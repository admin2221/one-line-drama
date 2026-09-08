# -*- coding: utf-8 -*-
"""AI 实时创作助手（Agent）。

用户用自然语言下达创作需求（如「帮我生成一张古风武侠图，然后做成15秒打斗短视频」），
Agent 完成：
1. LLM 拆解任务为步骤计划（steps JSON）：①写提示词 → ②文生图（本机 Z-Image 或
   NVIDIA FLUX 云端）→ ③图生视频（MiniMax H3 dyt 工作流，含 17 帧废帧+裁剪）；
2. 逐步调用 ComfyUI API 提交任务并轮询队列；
3. 出错（显存不足/节点报错）时把错误日志交给 LLM 调整参数自动重试（降步数/降分辨率/
   缩时长/关超分/换种子），最多重试 2 次；
4. 完成后把图片、视频文件路径回传给用户。

实时交互：任务运行中用户随时发消息，Agent 在步骤间隙/轮询间隙处理——
可修改后续步骤（重新规划）、提出新任务、或只是问答；「停止」可中断当前 GPU 任务
（ComfyUI /interrupt）并取消剩余步骤。

本模块只依赖标准库 + factory 内轻量模块，GUI 可直接导入（LLM 走 ProviderClient）。
"""
import json
import os
import queue
import re
import threading
import time

from .client import ComfyClient
from .concat import trim_first_frames
from . import workflow_dyt

AGENT_DIR_NAME = "AI助手"
_VIDEO_ROOT = r"G:\视频输出"

# 步骤类型 → 中文名（GUI 展示）
TYPE_NAMES = {"image": "生成图片", "video": "生成视频"}

_ASPECT_MAP = {
    "9:16": "9:16 (Portrait Widescreen)",
    "16:9": "16:9 (Landscape Widescreen)",
    "1:1": "1:1 (Square)",
    "4:3": "4:3 (landscape)",
    "3:4": "3:4 (portrait)",
}


def default_out_root():
    try:
        os.makedirs(_VIDEO_ROOT, exist_ok=True)
        return _VIDEO_ROOT
    except Exception:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, "output")


def _extract_json(text):
    """从 LLM 回复中提取第一个 JSON 对象；失败返回 None。"""
    if not text:
        return None
    text = str(text)
    # 去掉 ```json 围栏
    m = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if m:
        text2 = m.group(1)
    else:
        text2 = text
    start = text2.find("{")
    if start < 0:
        return None
    # 括号配平扫描
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text2)):
        ch = text2[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text2[start:i + 1])
                except Exception:
                    return None
    return None


class Agent:
    """一次会话一个实例；run() 在工作线程执行，GUI 通过 emit 回调收事件。"""

    MAX_RETRY = 2

    def __init__(self, emit=None, provider=None, comfy_url="http://127.0.0.1:8188",
                 image_backend="local", image_api_config=None, out_root=None,
                 log=None):
        self.emit = emit or (lambda **kw: None)
        self.provider = provider          # ProviderClient 或 None（规则模式）
        self.image_backend = image_backend
        self.image_api_config = image_api_config
        self.log = log or (lambda s: None)
        self.client = ComfyClient(base_url=comfy_url)
        self.out_dir = os.path.join(out_root or default_out_root(), AGENT_DIR_NAME,
                                    time.strftime("%Y%m%d_%H%M%S"))
        os.makedirs(self.out_dir, exist_ok=True)
        self.msgs = queue.Queue()         # 用户实时消息
        self.cancel = threading.Event()       # 取消整个任务
        self.interrupt_step = threading.Event()  # 中断当前步（GPU 任务）
        self.busy = False
        self.plan = None
        self.state_path = os.path.join(self.out_dir, "agent_state.json")

    # ---------------- 用户入口 ----------------
    def send(self, text):
        """GUI 线程调用：投递实时消息（运行中排队，步骤间隙处理）。"""
        if text and text.strip():
            self.msgs.put(text.strip())

    def stop(self):
        """停止：中断当前 GPU 任务 + 取消剩余步骤。"""
        self.cancel.set()
        self.interrupt_step.set()
        try:
            self.client.interrupt()
        except Exception:
            pass

    # ---------------- 事件 / 状态 ----------------
    def _emit(self, etype, **kw):
        try:
            self.emit(type=etype, **kw)
        except Exception:
            pass

    def _save_state(self):
        try:
            st = {"plan": self.plan, "out_dir": self.out_dir,
                  "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")}
            tmp = self.state_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(st, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.state_path)
        except Exception:
            pass

    # ---------------- LLM ----------------
    def _chat(self, system, user, temperature=0.3, max_tokens=2048):
        """LLM 调用；无提供商或失败返回 None（调用方走兜底逻辑）。"""
        if self.provider is None:
            return None
        try:
            return self.provider.chat(system, user, temperature=temperature,
                                      max_tokens=max_tokens)
        except Exception as e:
            self.log(f"[AI助手] LLM 调用失败：{e}")
            return None

    # ---------------- 任务拆解 ----------------
    _PLAN_SYS = (
        "你是短视频创作流水线的任务规划师。把用户的需求拆解为步骤计划，只输出 JSON：\n"
        '{"title":"简短标题","reply":"给用户的一两句话确认(说明你将做什么)",'
        '"steps":[{"type":"image","name":"步骤名","prompt":"英文文生图提示词(含主体/服饰/场景/'
        '光影/风格/画质词)","aspect":"9:16|16:9|1:1","size":"1024x1024(可选)"},'
        '{"type":"video","name":"步骤名","image_step":0(引用前面图片步骤的序号,可省略),'
        '"prompt":"中文导演式视频提示词(主体动作分解/镜头运动/氛围声景,可写(0-5秒)(5-10秒)分段)",'
        '"duration_sec":15,"aspect":"9:16"}]}\n'
        "规则：\n"
        "1. 视频步骤必须依赖一张图片（用 image_step 引用，或先安排 image 步骤）；\n"
        "2. duration_sec 上限 15 秒；用户说 N 秒就用 N；\n"
        "3. 视频提示词用中文导演式（含镜头语言/动作时段/情绪）；图片提示词用英文；\n"
        "4. 只输出 JSON，不要多余文字。"
    )

    def make_plan(self, user_text):
        """需求 → 步骤计划。LLM 失败时走规则兜底。"""
        raw = self._chat(self._PLAN_SYS, user_text, temperature=0.4, max_tokens=1600)
        data = _extract_json(raw)
        if not data or not isinstance(data.get("steps"), list) or not data["steps"]:
            self.log("[AI助手] LLM 拆解失败或无效，使用规则解析兜底")
            return self._rule_plan(user_text)
        steps = []
        for s in data["steps"]:
            if not isinstance(s, dict) or s.get("type") not in ("image", "video"):
                continue
            steps.append(self._norm_step(s))
        if not steps:
            return self._rule_plan(user_text)
        return {"title": str(data.get("title") or "AI助手任务"),
                "reply": str(data.get("reply") or ""),
                "steps": steps}

    def _norm_step(self, s):
        t = s.get("type")
        out = {"type": t, "name": str(s.get("name") or TYPE_NAMES.get(t, t)),
               "prompt": str(s.get("prompt") or "").strip()}
        if t == "image":
            out["aspect"] = str(s.get("aspect") or "1:1")
            out["size"] = str(s.get("size") or "1024x1024")
            out["retries"] = 0
        else:
            try:
                d = float(s.get("duration_sec") or 5)
            except Exception:
                d = 5.0
            d = max(1.0, min(15.0, d))
            out["duration_sec"] = d
            out["aspect"] = str(s.get("aspect") or "9:16")
            img_step = s.get("image_step")
            out["image_step"] = int(img_step) if isinstance(img_step, (int, float)) else None
            out["retries"] = 0
        return out

    def _rule_plan(self, user_text):
        """无 LLM 兜底：关键词解析（图/视频/秒数）。"""
        text = user_text.strip()
        m = re.search(r"(\d+)\s*秒", text)
        dur = int(m.group(1)) if m else 5
        dur = max(1, min(15, dur))
        wants_vid = any(k in text for k in ("视频", "短片", "动画", "动起来", "做成"))
        wants_img = any(k in text for k in ("图", "海报", "壁纸", "画"))
        steps = []
        if wants_img or not wants_vid:
            steps.append({"type": "image", "name": "图片", "prompt": text,
                          "aspect": "1:1", "size": "1024x1024", "retries": 0})
        if wants_vid:
            steps.append({"type": "video", "name": f"{dur}秒视频", "prompt": text,
                          "duration_sec": float(dur), "aspect": "9:16",
                          "image_step": 0 if steps else None, "retries": 0})
        return {"title": "AI助手任务", "reply": "", "steps": steps}

    # ---------------- 实时消息分类 ----------------
    def _handle_msgs(self, steps, done_idx):
        """步骤间隙处理用户实时消息。返回 (new_steps, next_idx)；
        cancel 置位时由外层处理。"""
        msgs = []
        while True:
            try:
                msgs.append(self.msgs.get_nowait())
            except queue.Empty:
                break
        for text in msgs:
            act = self._classify(text, running=True)
            a = act.get("action")
            if a == "cancel":
                self.cancel.set()
                self._emit("log", text="收到停止指令，取消剩余步骤")
                return steps, done_idx
            if a == "modify":
                new_steps = self._replan(steps, done_idx, text)
                if new_steps is not None:
                    self.plan["steps"] = steps[:done_idx] + new_steps
                    self._save_state()
                    self._emit("plan", title=self.plan.get("title"),
                               steps=self.plan["steps"], done=done_idx,
                               text=f"已按你的要求调整剩余步骤（{len(new_steps)} 步）")
                    return self.plan["steps"], done_idx
            elif a == "new":
                # 当前计划作废（保留已完成文件），重新规划
                self._emit("log", text="收到新任务，取消剩余步骤并重新规划")
                newp = self.make_plan(text)
                self.plan = newp
                self._save_state()
                self._emit("plan", title=newp.get("title"), steps=newp["steps"],
                           done=0, text=newp.get("reply") or "开始新任务")
                return newp["steps"], 0
            else:
                self._emit("reply", text=act.get("reply")
                           or f"收到：{text}（将在当前步骤结束后生效/参考）")
        return steps, done_idx

    def _classify(self, text, running):
        raw = self._chat(
            "你是创作助手的意图分类器。根据用户消息返回 JSON："
            '{"action":"modify|new|cancel|chat","reply":"一句话回复(chat/modify时给用户)"，'
            '"instruction":"modify 时给规划师的修改要求"}\n'
            "分类规则：要求停止/取消=cancel；对正在执行/后续步骤的调整（改提示词/时长/风格/重画）=modify；"
            "全新创作需求=new；提问/闲聊/问进度=chat。只输出 JSON。", text, temperature=0.1)
        data = _extract_json(raw)
        if data and data.get("action") in ("modify", "new", "cancel", "chat"):
            return data
        low = text.lower()
        if any(k in text for k in ("停止", "取消", "别生成", "中断")) or low in ("stop",):
            return {"action": "cancel"}
        if any(k in text for k in ("改", "换", "重", "调整", "再", "加点", "去掉", "改成")):
            return {"action": "modify", "instruction": text}
        return {"action": "chat", "reply": f"收到：{text}"}

    def _replan(self, steps, done_idx, instruction):
        """按用户要求重新规划剩余步骤。"""
        remaining = steps[done_idx:]
        raw = self._chat(
            self._PLAN_SYS,
            "原计划剩余步骤 JSON：\n" + json.dumps(remaining, ensure_ascii=False)
            + "\n\n用户修改要求：" + instruction
            + "\n\n返回修改后的完整剩余步骤 JSON（保持格式一致，未提及的部分尽量保留）。",
            temperature=0.4)
        data = _extract_json(raw)
        if not data or not isinstance(data.get("steps"), list) or not data["steps"]:
            self._emit("reply", text="没能理解修改要求，继续按原计划执行")
            return None
        out = []
        for s in data["steps"]:
            if isinstance(s, dict) and s.get("type") in ("image", "video"):
                out.append(self._norm_step(s))
        return out or None

    # ---------------- 出错重试 ----------------
    def _fix_step(self, step, err):
        """错误日志 → LLM 调参；失败走启发式。返回调整后的步骤或 None（放弃）。"""
        r = int(step.get("retries") or 0)
        raw = self._chat(
            "你是 ComfyUI 生成任务调参器。任务 JSON 执行报错，请调整参数后只输出调整后的"
            "完整步骤 JSON（格式不变）。常见手段：降低 steps、降低分辨率(size/megapixels)、"
            "缩短 duration_sec、upscale 改 off、换 seed、简化 prompt。"
            "若是显存不足(OOM/out of memory/CUDA)务必降低分辨率与时长。",
            "步骤 JSON：\n" + json.dumps(step, ensure_ascii=False)
            + "\n\n错误日志：\n" + str(err)[:900], temperature=0.2)
        data = _extract_json(raw)
        if data and data.get("type") == step.get("type"):
            fixed = self._norm_step(data)
            fixed["retries"] = r + 1
            return fixed
        # 启发式兜底
        fixed = dict(step)
        fixed["retries"] = r + 1
        if step["type"] == "video":
            fixed["duration_sec"] = max(2.0, float(step.get("duration_sec") or 5) * 0.6)
            if r >= 1:
                fixed["upscale"] = "off"
        else:
            w, h = "1024", "1024"
            m = re.match(r"(\d+)x(\d+)", str(step.get("size") or ""))
            if m:
                w, h = m.group(1), m.group(2)
            fixed["size"] = f"{max(384, int(int(w) * 0.7) // 64 * 64)}x{max(384, int(int(h) * 0.7) // 64 * 64)}"
            if r >= 1:
                fixed["seed"] = int(time.time()) % (2 ** 31)
        return fixed

    # ---------------- ComfyUI 执行 ----------------
    def _run_api(self, api, on_poll=None):
        """提交 + 轮询；支持实时消息注入与中断。返回 history entry；失败抛 RuntimeError。"""
        pid = self.client.queue_prompt(api)["prompt_id"]
        while True:
            entry = self.client.wait_done(pid, max_wait=8)
            if "error" in entry and entry.get("error") == "timeout":
                # 8 秒未结束：处理实时消息/中断检查后继续轮询
                if self.interrupt_step.is_set():
                    try:
                        self.client.interrupt()
                    except Exception:
                        pass
                if not self.msgs.empty():
                    self._emit("log", text="（任务运行中收到你的消息，当前步骤结束后处理）")
                if on_poll:
                    try:
                        on_poll()
                    except Exception:
                        pass
                continue
            if "error" in entry:
                err = str(entry.get("error"))
                e = entry.get("entry") or {}
                msgs = (e.get("status") or {}).get("messages") or []
                try:
                    err += " | " + json.dumps(msgs, ensure_ascii=False)[:600]
                except Exception:
                    pass
                raise RuntimeError(err)
            return entry

    def _exec_image(self, step, idx):
        size = str(step.get("size") or "1024x1024")
        try:
            w, h = [max(256, int(x)) for x in size.lower().split("x")]
        except Exception:
            w = h = 1024
        local = os.path.join(self.out_dir, f"image_{idx:02d}.png")
        from factory import generator as _g  # 延迟导入（模块较重）
        if self.image_backend == "api":
            from . import nvidia_api
            cfg = nvidia_api.load_image_api_config(self.image_api_config)
            cli = nvidia_api.NvidiaFluxClient(config=cfg)
            raw = cli.generate_image(step["prompt"], width=w, height=h)
            with open(local, "wb") as f:
                f.write(raw)
        else:
            api = _g.build_zimage_prompt(step["prompt"],
                                         f"ai_agent/img_{idx:02d}", width=w, height=h)
            entry = self._run_api(api)
            fn, sub, typ = self.client.first_image(entry)
            if not fn:
                raise RuntimeError("未获取到图片输出")
            self.client.view_image(fn, sub, typ, save_to=local)
        return local

    def _exec_video(self, step, idx, steps):
        # 参考图：image_step 指定或最近完成的图片
        img_ref = None
        isi = step.get("image_step")
        if isinstance(isi, int) and 0 <= isi < len(steps):
            img_ref = steps[isi].get("output")
        if not img_ref:
            for s in reversed(steps[:idx]):
                if s.get("type") == "image" and s.get("output"):
                    img_ref = s["output"]
                    break
        if not img_ref or not os.path.isfile(img_ref):
            raise RuntimeError("视频步骤缺少参考图片（前序图片步骤未完成）")
        up = self.client.upload_image(img_ref)
        iname = up.get("name")
        if not iname:
            raise RuntimeError("参考图上传 ComfyUI 失败")
        from factory import generator as _g
        aspect = _ASPECT_MAP.get(str(step.get("aspect") or "9:16"),
                                 "9:16 (Portrait Widescreen)")
        params = {"megapixels": 0.2, "aspect_ratio": aspect,
                  "workflow": workflow_dyt.default_workflow_path(),
                  "minimax_mode": "dyt"}
        if step.get("upscale"):
            params["upscale"] = step["upscale"]
        shot = {"shot": idx, "duration_sec": float(step.get("duration_sec") or 5),
                "_script": {}}
        api = workflow_dyt.build_shot_video_api(shot, [iname], params)
        warm = int(params.get("warmup_frames") or 0)
        entry = self._run_api(api)
        fn, sub, typ = self.client.first_image(entry)
        if not fn or not str(fn).lower().endswith((".mp4", ".webm", ".mov")):
            # first_image 可能拿到图片（预览），改用媒体查找
            for nid, outs in (entry.get("outputs") or {}).items():
                for k, v in (outs or {}).items():
                    if isinstance(v, list):
                        for item in v:
                            if isinstance(item, dict) and str(item.get("filename", "")).lower().endswith(
                                    (".mp4", ".webm", ".mov")):
                                fn, sub, typ = item["filename"], item.get("subfolder", ""), item.get("type", "output")
            if not fn:
                raise RuntimeError("未获取到视频输出")
        raw = os.path.join(self.out_dir, f"video_{idx:02d}.warm.mp4")
        self.client.view_image(fn, sub, typ, save_to=raw)
        local = os.path.join(self.out_dir, f"video_{idx:02d}.mp4")
        if warm > 0 and trim_first_frames(raw, local, n=warm):
            try:
                os.remove(raw)
            except Exception:
                pass
        else:
            os.replace(raw, local)
        return local

    def _exec_with_retry(self, step, idx, steps):
        while True:
            try:
                if step["type"] == "image":
                    return self._exec_image(step, idx)
                return self._exec_video(step, idx, steps)
            except Exception as e:
                r = int(step.get("retries") or 0)
                if self.cancel.is_set() or self.interrupt_step.is_set():
                    raise RuntimeError("已取消")
                if r > self.MAX_RETRY:
                    raise
                self._emit("log", text=f"步骤「{step.get('name')}」失败：{str(e)[:200]}，尝试自动调参重试（{r + 1}/{self.MAX_RETRY}）…")
                self.interrupt_step.clear()
                fixed = self._fix_step(step, str(e))
                step.clear()
                step.update(fixed)

    # ---------------- 主循环 ----------------
    def run(self, user_text):
        """在工作线程执行。"""
        if self.busy:
            self._emit("reply", text="当前有任务正在执行，请先等它完成或点停止。")
            return
        self.busy = True
        self.cancel.clear()
        self.interrupt_step.clear()
        try:
            self._run(user_text)
        except Exception as e:
            self._emit("error", text=f"任务异常终止：{str(e)[:300]}")
        finally:
            self.busy = False

    def _run(self, user_text):
        try:
            h = self.client.health()
            if "error" in h or "comfyui_version" not in h:
                self._emit("error", text=f"ComfyUI 未连接（{self.client.base_url}），无法执行生成任务")
                return
        except Exception as e:
            self._emit("error", text=f"ComfyUI 未连接：{e}")
            return
        self._emit("log", text=f"任务目录：{self.out_dir}")
        plan = self.make_plan(user_text)
        self.plan = plan
        self._save_state()
        self._emit("plan", title=plan.get("title"), steps=plan["steps"], done=0,
                   text=plan.get("reply") or f"已拆解为 {len(plan['steps'])} 个步骤")
        if not plan["steps"]:
            self._emit("reply", text="没能从你的需求中识别出生成任务，试试描述要生成的图片或视频。")
            return
        steps = plan["steps"]
        outputs = []
        i = 0
        while i < len(steps):
            if self.cancel.is_set():
                self._emit("done", ok=False, text="已取消", outputs=outputs)
                return
            steps, i = self._handle_msgs(steps, i)
            if self.cancel.is_set():
                self._emit("done", ok=False, text="已取消", outputs=outputs)
                return
            if i >= len(steps):
                break
            step = steps[i]
            self._emit("step_start", index=i, name=step.get("name"),
                       typ=TYPE_NAMES.get(step["type"], step["type"]))
            t0 = time.time()
            try:
                out = self._exec_with_retry(step, i, steps)
            except Exception as e:
                if self.cancel.is_set():
                    self._emit("done", ok=False, text="已取消", outputs=outputs)
                else:
                    self._emit("step_fail", index=i, name=step.get("name"), text=str(e)[:300])
                    self._emit("done", ok=False,
                               text=f"步骤「{step.get('name')}」多次重试后仍失败，任务终止",
                               outputs=outputs)
                return
            step["output"] = out
            outputs.append({"index": i, "type": step["type"], "name": step.get("name"),
                            "path": out})
            self._save_state()
            i += 1
            self._emit("step_done", index=i - 1, name=step.get("name"), path=out,
                       secs=f"{time.time() - t0:.0f}")
            steps, i = self._handle_msgs(steps, i)
            # _handle_msgs 可能重置计划（新任务），同步索引
        self._emit("done", ok=True, text="全部完成", outputs=outputs)
