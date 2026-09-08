# -*- coding: utf-8 -*-
"""短剧工厂 —— 一键生成完整竖屏短剧。

流程：
  一句话 -> LLM 剧本导演（含角色定妆 + 分镜）
          -> LLM 视觉概念设计师增强 -> Z-Image 生成角色定妆图
          -> 逐镜头 H3 ref2va 生成视频（共用定妆图 <Picture 1>，原生音频）
          -> 全部镜头自动 ffmpeg 拼接 -> 完整短剧

用法示例：
  python -m factory.drama_factory "一个落魄书生在雨夜捡到一枚能穿越时空的古镜"
  python -m factory.drama_factory --story "..." --resume --steps 20 --megapixels 0.6
"""
import argparse
import json
import os
import random
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

# 兼容直接运行 (python factory/drama_factory.py) 与模块运行 (python -m factory.drama_factory)
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from factory import generator
    from factory.client import ComfyClient
    from factory.concat import concat_videos, trim_first_frames
    from factory.prompts import SCRIPT_DIRECTOR_PROMPT
    from factory import toonflow_skills
    from factory import nvidia_api
    from factory import task_state
else:
    from . import generator
    from .client import ComfyClient
    from .concat import concat_videos, trim_first_frames
    from .prompts import SCRIPT_DIRECTOR_PROMPT
    from . import toonflow_skills
    from . import nvidia_api
    from . import task_state

HERE = os.path.dirname(os.path.abspath(__file__))
# 默认输出根目录：G:/视频输出（每次任务在其下新建时间戳子目录，防止旧数据被覆盖）。
# G 盘不可用时回退 exe 同目录 output\（避免落进临时解压目录）。
_VIDEO_ROOT = r"G:\视频输出"
def _default_output_root():
    try:
        os.makedirs(_VIDEO_ROOT, exist_ok=True)
        return _VIDEO_ROOT
    except Exception:
        pass
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "output")
    return os.path.join(os.path.dirname(HERE), "output")
DEFAULT_OUTPUT_ROOT = _default_output_root()


def parse_json_block(text):
    """从 LLM 输出中容错提取 JSON（容忍 markdown code fence / 前后缀 / 思考文本）。

    Qwen3.8 的思考外溢文本可能包含花括号，用栈匹配定位完整 JSON 对象区间，
    并从后往前尝试解析（答案 JSON 通常在输出末尾）。
    """
    if not text:
        return None
    text = text.strip()
    # 去掉 ```json ... ``` 包裹
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()

    def scan_objects(s):
        """返回 (start, end) 列表：所有成对的 {…} 区间（按出现顺序）。"""
        objs = []
        stack = []
        in_str = False
        esc = False
        for i, c in enumerate(s):
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == "{":
                    stack.append(i)
                elif c == "}":
                    if stack:
                        objs.append((stack.pop(), i))
        return objs

    for s, e in reversed(scan_objects(text)):
        candidate = text[s:e + 1]
        try:
            return json.loads(candidate)
        except Exception:
            continue
    # 兼容历史路径：旧算法（首 { 到末 }）
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        candidate = text[start:end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            fixed = re.sub(r",\s*([}\]])", r"\1", candidate)
            try:
                return json.loads(fixed)
            except Exception:
                return None
    return None


def _collect_scenes(script):
    """收集去重的核心场景参考图列表，返回 [(场景名, 描述)]。

    优先用脚本顶层 scenes 字典（每键一个核心场景，各生成一张参考图）。
    若剧本没有 scenes 字典，则退化为逐镜头 scene 去重。
    """
    scenes_d = script.get("scenes") or {}
    if scenes_d:
        return [(k, v) for k, v in scenes_d.items() if str(k).strip()]
    # 退化：逐镜头 scene 字段去重
    seen = {}
    for s in script.get("shots", []):
        sc = (s.get("scene") or "").strip()
        if not sc or sc in seen:
            continue
        ip = s.get("image_prompt", "").strip()
        seen[sc] = " ".join(ip.split()[:60]) if ip else sc
    return list(seen.items())


def _collect_props(script):
    """收集去重的关键物品参考图列表，返回 [(物品名, 描述)]。

    优先用脚本顶层 props 字典（每键一个物品，各生成一张参考图）。
    若剧本没有 props 字典，则从镜头 props 字段收集。
    """
    props_d = script.get("props") or {}
    if props_d:
        return [(k, v) for k, v in props_d.items() if str(k).strip()]
    seen = {}
    for s in script.get("shots", []):
        for p in s.get("props", []):
            key = p if isinstance(p, str) else (p.get("name") or "")
            key = str(key).strip()
            if not key or key in seen:
                continue
            if isinstance(p, dict) and p.get("prompt"):
                seen[key] = p["prompt"]
            else:
                seen[key] = f"a close-up of {key}, cinematic, consistent lighting"
    return list(seen.items())


def _assemble_shot_refs(shot, refs_result):
    """为一个镜头组装参考图文件名列表和 <Picture N> 标签映射。

    返回 (ref_images, refs)：
      ref_images: [input文件名, ...]，顺序对应 <Picture 1..N>
      refs      : dict {"character": "<Picture X>", "scene": ..., "prop": ...}

    图序：出场角色（按 characters 顺序匹配）→ 场景 → 物品。
    """
    ref_images, refs = [], {}

    # 角色：该镜头出现的角色（character_refs 或回退全部）
    ch = shot.get("character_refs") or shot.get("characters")
    char_all = refs_result.get("character_all") or []
    chars = shot.get("_script_chars")  # 可能由调用方注入
    names = [c.get("name", "") for c in (chars or [])]
    char_pics = {}  # {角色名: <Picture N>}
    if ch:
        # character_refs 为角色名列表，按 characters 顺序定位
        for cname in ch:
            idx = names.index(cname) if cname in names else None
            if idx is not None and idx < len(char_all) and char_all[idx]:
                ref_images.append(char_all[idx])
                char_pics[cname] = f"<Picture {len(ref_images)}>"
    # 若没明确指定或没匹配到，退回全部角色图（仍记录每张图对应角色名）
    if not ref_images:
        for ci, img in enumerate(char_all):
            if img:
                ref_images.append(img)
                cn = names[ci] if ci < len(names) else f"角色{ci + 1}"
                char_pics[cn] = f"<Picture {len(ref_images)}>"

    if ref_images:
        refs["character"] = "<Picture {0}>"

    # 场景
    sc = shot.get("scene_ref") or shot.get("scene")
    if sc:
        img = refs_result.get("scene_map", {}).get(sc)
        if img:
            ref_images.append(img)
            refs["scene"] = f"<Picture {len(ref_images)}>"

    # 物品（可多个）
    props = shot.get("prop_refs") or shot.get("props")
    if props:
        for p in props:
            key = p if isinstance(p, str) else (p.get("name") or "")
            key = str(key).strip()
            img = refs_result.get("prop_map", {}).get(key)
            if img:
                ref_images.append(img)
                refs[f"prop_{key}"] = f"<Picture {len(ref_images)}>"

    # 角色标签用实际序号补齐；并为每个出场角色登记独立标签（供对白说话人绑定）
    if refs.get("character"):
        refs["character"] = refs["character"].format(1)
    for cname, tag in char_pics.items():
        refs[f"char_{cname}"] = tag
    return ref_images, refs


def run_and_get_text(client, api):
    """提交并等待，返回 first_text。"""
    pid = client.queue_prompt(api)["prompt_id"]
    entry = client.wait_done(pid)
    if "error" in entry:
        raise RuntimeError(f"LLM 执行失败：{entry.get('error')}")
    return client.first_text(entry)


def run_and_get_outputs(client, api):
    """提交并等待，返回 history entry（含 outputs）。"""
    pid = client.queue_prompt(api)["prompt_id"]
    entry = client.wait_done(pid)
    if "error" in entry:
        raise RuntimeError(f"执行失败：{entry.get('error')}")
    return entry


def find_media(entry, exts=(".png", ".jpg", ".jpeg", ".webp", ".mp4", ".webm", ".mov")):
    """从 history entry 提取第一个媒体文件 (filename, subfolder, type)。"""
    for nid, outs in entry.get("outputs", {}).items():
        if not isinstance(outs, dict):
            continue
        for k, v in outs.items():
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, dict) and "filename" in item:
                        fn = item.get("filename", "")
                        if fn.lower().endswith(exts):
                            return fn, item.get("subfolder", ""), item.get("type", "output")
    return None, None, None


def _enforce_char_count(script, log=None):
    """校验并规范化剧本角色数量为 2-15 个。

    - 顶层 characters（list[{"name","prompt"}]）优先
    - 缺失时用 character 字段补成主角
    - 超 15 个截断、不足 2 个时尝试从 character 拆分补足；仍不足则保留现状并警告
    返回 (script, ok)。
    """
    ok = True
    chars = script.get("characters")
    if not isinstance(chars, list):
        chars = []
    # 清洗：去掉没有 name/prompt 的项
    chars = [c for c in chars if isinstance(c, dict) and (c.get("name") or "").strip()
             and (c.get("prompt") or "").strip()]
    # 用 character 字段补主角（若没进列表）
    c0 = (script.get("character") or "").strip()
    if c0 and not any((c.get("prompt") or "").strip() == c0 for c in chars):
        main_name = chars[0].get("name") if chars else "主角"
        chars.insert(0, {"name": main_name, "prompt": c0})
    if len(chars) > 15:
        if log:
            log(f"  [i] 角色数 {len(chars)} 超出上限 15，截断保留前 15 个")
        chars = chars[:15]
        ok = False
    elif len(chars) < 2:
        if log:
            log(f"  [i] 角色数 {len(chars)} 不足 2 个，已尽量补充")
        ok = False
    script["characters"] = chars
    if chars:
        script["character"] = chars[0]["prompt"]  # 主角定妆保持与 characters[0] 一致
    return script, ok


def _parse_review_result(text):
    """解析 AI 审核返回的（修改建议或新剧本）。返回 dict 或 None。"""
    if not text:
        return None
    out = parse_json_block(text)
    if isinstance(out, dict) and ("shots" in out or "characters" in out or "review" in out):
        return out
    return None


class DramaFactory:
    def __init__(self, client, output_dir, args):
        self.client = client
        self.output_dir = output_dir
        self.args = args
        self.llm = getattr(args, "llm", None) or generator.LLM_DEFAULT
        # 自定义 OpenAI 兼容提供商（可选）：配置了则剧本推理/文生图走远程 API
        self.provider = None
        try:
            from factory import provider as _provider
            cfg = _provider.pick_provider(
                name=getattr(args, "provider", None),
                path=getattr(args, "provider_config", None))
            if cfg:
                self.provider = _provider.ProviderClient(cfg, log=self.log)
                self.log(f"自定义提供商已启用：{cfg.get('name')} "
                         f"(chat={cfg.get('chat_model')}, image={cfg.get('image_model')})")
        except Exception as e:
            self.log(f"[warn] 提供商初始化失败，继续用本机 ComfyUI：{e}")
        # 用户显式选择"自定义模型(API推理接口)"但未配置/未启用提供商 -> 阻止进入会走本地 LLM 的路径
        if self.llm == "custom" and self.provider is None:
            raise RuntimeError(
                "剧本 LLM 选择了“自定义模型(API推理接口)”，但未检测到可用的自定义提供商配置。\n"
                "请在 GUI 的“提供商设置”中填写 模型名称/API地址/APIKey/模型标识 并保存"
                "（providers.json），或通过 --provider-config 指定配置文件。")
        self.shots_dir = os.path.join(output_dir, "shots")
        os.makedirs(self.shots_dir, exist_ok=True)
        # NVIDIA 云端生图后端（--image-backend api 时启用）：参考图改走 FLUX API
        self.image_backend = getattr(args, "image_backend", None) or "local"
        self.image_api_cfg_path = getattr(args, "image_api_config", None)
        self._nvidia_cli = None
        if self.image_backend == "api":
            self.log("生图方式：NVIDIA FLUX API（角色定妆/场景/物品参考图走云端）")
        else:
            self.log("生图方式：本机 ComfyUI Z-Image（角色定妆/场景/物品参考图走本地）")

    def nvidia(self):
        """返回 NvidiaFluxClient（懒加载配置）；未配置时抛带指引的 RuntimeError。"""
        if self._nvidia_cli is not None:
            return self._nvidia_cli
        cfg = nvidia_api.load_image_api_config(path=self.image_api_cfg_path)
        if not cfg:
            raise RuntimeError(
                "已开启“API 生图”，但未找到 NVIDIA 生图 API 配置（image_api.json）。\n"
                "请在 GUI 的“生图API设置…”中填写 接口地址/APIKey 并保存，"
                "或用 --image-api-config 指定配置文件。")
        try:
            self._nvidia_cli = nvidia_api.NvidiaFluxClient(cfg, log=self.log)
        except nvidia_api.NvidiaFluxError as e:
            raise RuntimeError(f"NVIDIA 生图 API 配置无效：{e}") from e
        self.log(f"  NVIDIA 生图 API：{self._nvidia_cli.endpoint} "
                 f"（{self._nvidia_cli.width}×{self._nvidia_cli.height}，"
                 f"steps={self._nvidia_cli.steps}）")
        return self._nvidia_cli

    def log(self, msg):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

    def _minimax_prompt_extra(self):
        """根据 --minimax-template / --dialogue-ratio 生成追加到剧本提示词的约束文本。

        返回字符串；无启用时返回空串。
        """
        extra = []
        mm = getattr(self.args, "minimax_template", None)
        dlg = float(getattr(self.args, "dialogue_ratio", 0.0) or 0.0)
        if mm:
            if mm == "director":
                extra.append(
                    "【六段式+导演台】最终每镜头将改写为 MiniMax-H3 六段式提示词"
                    "（主体定义/摘要/保留分析/详细描述/整体声景/非叙事配乐），全片共享公共主体定义，"
                    "逐镜头之间必须“无硬切。紧接上一段。”并停在稳定收尾手势，保证分镜动作连续、位置连贯、不跳切。")
            elif mm == "dyt":
                extra.append(
                    "【dyt 工作流模板——最高优先级，覆盖上方 video_prompt 的英文≤40词要求】"
                    "本剧采用 dyt.json（MiniMax H3 fl2va）工作流，最终每镜头将按其中文导演式提示词生成："
                    "video_prompt 必须用中文，直接以（X-Y秒）分段写出画面动作、运镜与情绪"
                    "（如（0-3秒）阿杰骑车从雨幕中驶来，镜头侧面跟随；（3-6秒）…），"
                    "各段时间相加必须等于该镜头 duration，必要时在动作前标注 图1/图2 参考图序号，"
                    "对白放 dialogue_list 数组（每项 {'speaker','text'}，旁白 speaker 留空），只允许简体中文；"
                    "plot 提供情绪张力；position 必须写明本镜各角色画面站位（左/右/中）；"
                    "同一角色跨镜头服饰颜色必须一致。"
                    "【镜头提示词长度——严禁少于 500 字】每个镜头的 video_prompt 必须写足写满不少于 500 字，完整呈现本镜剧情："
                    "①本镜完整剧情动作分解（谁、在哪、做什么、怎么发生，逐步写到细节）；"
                    "②与上一镜的画面衔接（承接上一镜结尾的机位/动作/位置，无跳切，画面持续连贯）；"
                    "③出场人物外观一致锚定（脸型五官、发型发色、服饰款式与颜色与定妆参考图逐字一致，"
                    "写明面部特写与表情控制要求，保证人物一致不崩脸）；"
                    "④人物的情绪描述与说话语气（如哽咽低语、怒斥、颤抖着喊、温柔微笑等，标注到每句台词与每段动作）；"
                    "⑤镜头语言（景别、运镜、光线、节奏）。"
                    "每个（X-Y秒）时段平均写 200 字左右，禁止一笔带过。")
            else:
                extra.append(
                    "【六段式模板】最终每镜头将改写为 MiniMax-H3 六段式提示词"
                    "（主体定义/摘要/保留分析/详细描述/整体声景/非叙事配乐）。"
                    "角色定妆、场景、物品描述要具体到能逐字锁定外观，供全片共享，增强视频连贯性与一致性。"
                    "video_prompt 需详尽充分：写清本镜完整剧情动作分解、与上一镜衔接（无跳切、画面持续连贯）、"
                    "出场人物外观锚定（脸型/发型/服饰颜色与定妆词逐字一致，不崩脸）、"
                    "人物情绪描述与说话语气、景别运镜与光线节奏（英文不少于 150 词，若用中文则不少于 500 字）。")
        if dlg > 0:
            pct = int(round(dlg * 100))
            extra.append(
                f"【对白占比——增强连贯性】全片对白口播时间必须占成片总时长 {pct}% 以上："
                f"几乎每个镜头都要有推动情节、有来有回的口语化对白，避免连续静默；"
                f"duration 与台词长度匹配，口播密集的镜可拉长、静默推进的镜要短。")
        return "\n\n".join(extra)

    def _attach_script_to_shots(self, script):
        """把整份剧本的公共上下文（角色/场景/物品/风格/配乐动机）注入每个 shot。

        只复制上下文字段、不复制 shots 列表，避免
        script -> shots -> shot._script -> script 的循环引用导致 json.dump 崩溃；
        供六段式重组时引用 characters/scenes/props/style/music_motif。
        """
        ctx = {
            "title": script.get("title"),
            "style": script.get("style"),
            "music_motif": script.get("music_motif"),
            "characters": script.get("characters") or [],
            "scenes": script.get("scenes") or {},
            "props": script.get("props") or {},
        }
        for s in script.get("shots", []):
            s["_script"] = ctx

    def _toonflow_constraint_blocks(self):  
        # Return (genre_block, art_block) text from --genre / --art-style args.  
        try:  
            from factory import prompts as _pr  
        except Exception:  
            _pr = None  
        genre_block = ''  
        art_block = ''  
        if _pr is not None:  
            genre_block = _pr.add_genre_director(getattr(self.args, 'genre', None))  
            art_block = _pr.add_art_style_prompt(getattr(self.args, 'art_style', None))  
        return genre_block, art_block  


    # ---------- 阶段 1：剧本 ----------
    def generate_script(self, story, chars=None):
        target = getattr(self.args, "target_seconds", None)
        if target and target >= 90:
            return self.generate_script_chunked(story, target, chars)

        # toonflow genre/art constraint blocks (after SCRIPT_DIRECTOR_PROMPT, before output discipline)  
        genre_block, art_block = self._toonflow_constraint_blocks()  
        director_prompt = SCRIPT_DIRECTOR_PROMPT  
        if genre_block or art_block:  
            _mk = '\u3010\u6700\u91cd\u8981\u3011'  
            if _mk in director_prompt:  
                _h, _t = director_prompt.split(_mk, 1)  
                director_prompt = _h + genre_block + art_block + _mk + _t  
            else:  
                director_prompt = director_prompt + genre_block + art_block    
        # 自定义提供商：剧本推理走 OpenAI 兼容 chat
        if self.provider is not None:
            # 与本地 LLM 路径一致：注入 dyt/六段式/对白占比约束
            _extra = self._minimax_prompt_extra()
            if _extra:
                director_prompt = director_prompt + "\n\n" + _extra
            self.log(f"阶段1/4：提供商剧本推理（{self.provider.chat_model}）…")
            text = self.provider.chat(director_prompt, story)
            if not text:
                raise RuntimeError("提供商 LLM 未返回任何文本")
            script = parse_json_block(text)
            if not script or "shots" not in script:
                raw = os.path.join(self.output_dir, "llm_raw.txt")
                with open(raw, "w", encoding="utf-8") as f:
                    f.write(text or "")
                raise RuntimeError(f"剧本 JSON 解析失败，原始输出已存至 {raw}")
            with open(os.path.join(self.output_dir, "script.json"), "w", encoding="utf-8") as f:
                json.dump(script, f, ensure_ascii=False, indent=2)
            script, _ = _enforce_char_count(script, log=self.log)
            n = len(script["shots"])
            chars = script.get("characters") or []
            total = sum(float(str(s.get("duration", "5")).strip() or 5) for s in script["shots"])
            self.log(f"  剧本《{script.get('title', '未命名')}》 共 {n} 个镜头，总时长约 {total:.0f}s，"
                     f"角色 {len(chars)} 个：{('、'.join(c.get('name','') for c in chars[:5]))[:40]}")
            return script
        self.log(f"阶段1/4：LLM 生成剧本（{self.llm}）…")
        # qwen3.8 系（27B）支持单次长输出（max_tokens 12000），qwen3.5 保持 4096
        cfg = generator.LLM_CONFIGS.get(self.llm, {})
        max_tokens = 12000 if cfg.get("n_ctx", 0) >= 16384 else 4096
        director_prompt = SCRIPT_DIRECTOR_PROMPT
        # 六段式/对白占比：在单次剧本导演提示词里追加约束
        extra = self._minimax_prompt_extra()
        if extra:
            director_prompt = director_prompt + "\n\n" + extra
        api = generator.build_script_prompt(story, director_prompt,
                                            max_tokens=max_tokens, llm=self.llm)
        text = run_and_get_text(self.client, api)
        if not text:
            raise RuntimeError("LLM 未返回任何文本")
        script = parse_json_block(text)
        if not script or "shots" not in script:
            # 保存原始输出供排查
            raw = os.path.join(self.output_dir, "llm_raw.txt")
            with open(raw, "w", encoding="utf-8") as f:
                f.write(text or "")
            raise RuntimeError(f"剧本 JSON 解析失败，原始输出已存至 {raw}")
        with open(os.path.join(self.output_dir, "script.json"), "w", encoding="utf-8") as f:
            json.dump(script, f, ensure_ascii=False, indent=2)
        script, _ = _enforce_char_count(script, log=self.log)
        self._attach_script_to_shots(script)
        n = len(script["shots"])
        total = sum(float(str(s.get("duration", "5")).strip() or 5) for s in script["shots"])
        est_min = total * 49 / 60  # 实测 ~49s GPU / 秒视频
        chars = script.get("characters") or []
        self.log(f"  剧本《{script.get('title', '未命名')}》 共 {n} 个镜头，总时长约 {total:.0f}s，"
                 f"预计 GPU 生成约 {est_min:.0f} 分钟")
        self.log(f"  角色 {len(chars)} 个：{('、'.join(c.get('name','') for c in chars[:5]))[:40]}")
        return script

    def generate_script_chunked(self, story, target, chars=None):
        """长剧分幕扩写：总纲（character/style/幕表）→ 逐幕展开镜头 → 合并。

        llama_cpp_parameters 的 max_tokens 硬上限 4096，单次装不下 45 镜头，
        因此先出总纲再逐幕扩写，每幕 4-5 镜头独立一次 LLM 调用。
        """
        import math
        genre_text = getattr(self.args, "genre", None) or ""
        art_text = getattr(self.args, "art_style", None) or ""
        n_shots = max(6, round(target / 11))  # 每镜约 8-15 秒，中值取 11
        n_beats = max(3, math.ceil(n_shots / 4.5))
        self.log(f"阶段1/4：长剧分幕扩写（{self.llm}，目标 {target}s，约 {n_shots} 镜头，{n_beats} 幕）…")

        # 1) 总纲：characters 由调用方预置，LLM 不生成
        mm = getattr(self.args, "minimax_template", None)
        dlg = float(getattr(self.args, "dialogue_ratio", 0.0) or 0.0)
        if self.provider is not None:
            # 远程提供商：直接 OpenAI 兼容 chat（构造与本地一致的 system prompt）
            from factory.prompts import outline_system_prompt
            sysp = outline_system_prompt(target, n_shots, n_beats, chars or [], None,
                                         minimax_mode=mm, dialogue_ratio=dlg or None,
                                         genre_text=genre_text, art_text=art_text)
            outline_text = self.provider.chat(sysp, story, temperature=0.2)
        else:
            outline_api = generator.build_outline_prompt(story, target, n_shots, n_beats,
                                                         chars or [], llm=self.llm,
                                                         minimax_mode=mm, dialogue_ratio=dlg or None,
                                                         genre_text=genre_text, art_text=art_text)
            outline_text = run_and_get_text(self.client, outline_api)
        outline = parse_json_block(outline_text)
        if not outline or "beats" not in outline:
            raw = os.path.join(self.output_dir, "llm_outline_raw.txt")
            with open(raw, "w", encoding="utf-8") as f:
                f.write(outline_text or "")
            raise RuntimeError(f"总纲 JSON 解析失败，原始输出已存至 {raw}")
        beats = outline["beats"]
        # 角色：优先调用方预置；否则取 LLM 在总纲中自拟的 2-15 个角色（含主角），
        # 不再回退到单个"主角"；仍无则临时兜底 1 个（_enforce_char_count 会尽量补足）
        if not chars:
            chars = outline.get("characters")
        if not isinstance(chars, list) or not chars:
            chars = [{"name": "主角", "prompt": "generic protagonist"}]
        # 规范化角色结构（含主角字段同步），总纲阶段即锁定 2-15 个角色
        chars, _ = _enforce_char_count({"characters": chars}, log=self.log)
        chars = chars["characters"]
        scenes_d = outline.get("scenes") or {}
        props_d = outline.get("props") or {}
        self.log(f"  总纲《{outline.get('title')}》 {len(beats)} 幕，"
                 f"角色：{len(chars)} 个，场景：{len(scenes_d)} 个，物品：{len(props_d)} 个")

        # 均衡分配每幕镜头数
        base, rem = divmod(n_shots, len(beats))
        counts = [base + (1 if i < rem else 0) for i in range(len(beats))]

        # 2) 逐幕展开；跨幕/跨段无缝衔接：记录上一幕末尾画面描述，传给下一幕首镜承接
        all_shots = []
        idx = 1
        prev_end = None
        for beat, cnt in zip(beats, counts):
            end = idx + cnt - 1
            self.log(f"  扩写第 {idx}-{end} 幕（{beat.get('scene', '')}，{cnt} 镜头）…")
            if self.provider is not None:
                from factory.prompts import segment_system_prompt
                sysp = segment_system_prompt(
                    outline.get("title", ""), "", outline.get("style", ""),
                    beat, idx, end, cnt,
                    characters=chars, scenes=scenes_d, props=props_d, prev_end=prev_end,
                    minimax_mode=getattr(self.args, "minimax_template", None),
                    dialogue_ratio=dlg or None, is_first=(idx == 1),
                    genre_text=genre_text, art_text=art_text)
                seg_text = self.provider.chat(
                    sysp, f"请扩写第 {idx} 到 {end} 幕镜头（共 {cnt} 个），并衔接上一段结尾。",
                    temperature=0.2)
            else:
                seg_api = generator.build_segment_prompt(
                    outline.get("title", ""), "", outline.get("style", ""),
                    beat, idx, end, cnt, llm=self.llm,
                    characters=chars, scenes=scenes_d, props=props_d, prev_end=prev_end,
                    minimax_mode=getattr(self.args, "minimax_template", None),
                    dialogue_ratio=dlg or None, is_first=(idx == 1),
                    genre_text=genre_text, art_text=art_text)
                seg_text = run_and_get_text(self.client, seg_api)
            seg = parse_json_block(seg_text)
            if not seg or "shots" not in seg:
                self.log(f"  [!] 第 {idx}-{end} 幕解析失败，重试一次…")
                if self.provider is not None:
                    # 提供商模式：seg_api 未定义，重试必须重调远程 chat，不能走本机 run_and_get_text
                    seg_text = self.provider.chat(
                        sysp, f"请扩写第 {idx} 到 {end} 幕镜头（共 {cnt} 个），并衔接上一段结尾。",
                        temperature=0.2)
                else:
                    seg_text = run_and_get_text(self.client, seg_api)
                seg = parse_json_block(seg_text)
            if not seg or "shots" not in seg:
                raise RuntimeError(f"第 {idx}-{end} 幕镜头展开失败，原始输出已存 llm_raw.txt")
            for s in seg["shots"]:
                s["shot"] = idx
                # 归一化引用字段
                if not s.get("scene_ref"):
                    s["scene_ref"] = s.get("scene", "")
                # 角色名别名归一化：把镜头里的角色名对齐到脚本 characters 的标准名
                if not s.get("character_refs"):
                    s["character_refs"] = [c.get("name", "") for c in chars]
                else:
                    std_names = [c.get("name", "") for c in chars]
                    cleaned = []
                    for r in s["character_refs"]:
                        r = str(r).strip()
                        if not r:
                            continue
                        if r in std_names:
                            cleaned.append(r)
                            continue
                        # 子串/包含匹配：找到唯一标准名
                        hit = [n for n in std_names if r in n or n in r]
                        cleaned.append(hit[0] if len(hit) == 1 else r)
                    s["character_refs"] = cleaned
                if not s.get("props"):
                    s["props"] = []
                # duration 兜底：LLM 漏给时默认 10（后续按秒计算与生成都依赖它）
                d = str(s.get("duration") or "").strip() or "10"
                try:
                    d = str(max(8, min(15, int(float(d)))))
                except (TypeError, ValueError):
                    d = "10"
                s["duration"] = d
                all_shots.append(s)
                idx += 1
            # 记录本幕末尾画面描述，供下一幕/下一段无缝衔接
            if seg["shots"]:
                last = seg["shots"][-1]
                _dlg_list = [d for d in (last.get("dialogue_list") or []) if isinstance(d, dict)]
                _dlg_txt = "、".join(f"{d.get('speaker', '')}：{d.get('text', '')}" for d in _dlg_list)
                prev_end = "场景: %s；动作/运镜: %s；对白: %s" % (
                    last.get("scene", ""), last.get("video_prompt", ""),
                    _dlg_txt or last.get("dialogue", ""))
                self.log(f"    （衔接上下文：{last.get('scene', '')}）")

        script = {
            "title": outline.get("title", "未命名"),
            "character": chars[0]["prompt"] if chars else "",
            "characters": chars,
            "style": outline.get("style", ""),
            "scenes": scenes_d,
            "props": props_d,
            "shots": all_shots,
        }
        with open(os.path.join(self.output_dir, "script.json"), "w", encoding="utf-8") as f:
            json.dump(script, f, ensure_ascii=False, indent=2)
        self._attach_script_to_shots(script)
        total = sum(float(str(s.get("duration", "5")).strip() or 5) for s in script["shots"])
        est_min = total * 49 / 60
        self.log(f"  剧本合并完成《{script['title']}》 共 {len(all_shots)} 个镜头，"
                 f"总时长约 {total:.0f}s，预计 GPU 生成约 {est_min:.0f} 分钟")
        return script

    # ---------- 本地 AI 审核 ----------
    def review_local(self, script_json, instruction="", max_tokens=4096):
        """用本地 LLM（走 ComfyUI llama 节点）审核并修改剧本。返回 (new_script, raw)。

        无自定义提供商时启用，保证"本地"智能体模式下 AI 审核可用。
        提示词与云端 review_script 保持一致。
        """
        import json as _json
        prompt = (
            "你是资深短剧编剧审稿人。请审核下面这份剧本 JSON，并直接输出【修改后的完整剧本 JSON】。\n"
            "要求：\n"
            "1. 保持 JSON 结构与原剧本一致（title/character/characters/style/shots 等字段都要保留）\n"
            "2. characters 数量保持在 2-15 个，角色不能多于 15 个\n"
            "3. 修复情节漏洞、台词生硬、逻辑不通、分镜衔接跳跃等问题；"
            "明显不合理或低质量处要直接改写，不要解释\n"
            "4. 若剧本已很好，可原样输出（不要添加 review 字段，输出结构必须与输入一致）\n"
            "5. 只输出 JSON，不要任何解释、前言或后语\n"
        )
        if instruction and instruction.strip():
            prompt += f"\n【用户补充修改要求】\n{instruction.strip()}\n"
        prompt += f"\n【剧本 JSON】\n{_json.dumps(script_json, ensure_ascii=False, indent=2)}\n"
        api = generator.build_script_prompt(prompt, "请输出修改后的完整剧本 JSON",
                                            max_tokens=max_tokens, temperature=0.4, llm=self.llm)
        text = run_and_get_text(self.client, api)
        return _parse_review_result(text), text

    # ---------- 阶段 2：定妆图 / 参考图 ----------
    # ---------- NVIDIA 云端生图（--image-backend api） ----------
    def _api_image(self, prompt_text, local_path, prefix):
        """NVIDIA FLUX 云端生图 -> 本地文件 -> 上传 ComfyUI input。返回 input 文件名。

        API 生图失败时返回 None（与本地失败跳过行为一致，槽位保留 None）。
        """
        try:
            raw = self.nvidia().generate_image(prompt_text)
        except Exception as e:
            self.log(f"  [!] API 生图失败（{prefix}），跳过该参考图：{e}")
            return None
        # 按实际图片格式对齐扩展名（FLUX 常返回 JPEG，避免 .png 名配 JPEG 内容）
        try:
            if raw[:3] == b"\xff\xd8\xff":
                ext = ".jpg"
            elif raw[:8] == b"\x89PNG\r\n\x1a\n":
                ext = ".png"
            elif raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
                ext = ".webp"
            else:
                ext = os.path.splitext(local_path)[1] or ".png"
            base, cur = os.path.splitext(local_path)
            if ext.lower() != cur.lower():
                local_path = base + ext
            os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
            with open(local_path, "wb") as f:
                f.write(raw)
        except Exception as e:
            self.log(f"  [!] 本地保存失败（{local_path}）：{e}")
            return None
        self.log(f"    API 参考图已保存：{os.path.basename(local_path)}（{len(raw) // 1024} KB）")
        try:
            up = self.client.upload_image(local_path)
        except Exception as e:
            self.log(f"  [!] 上传 ComfyUI 失败（{local_path}）：{e}")
            return None
        iname = up.get("name")
        if iname:
            self.log(f"    参考图已上传：input/{iname}")
        return iname

    # ---------- 阶段 2：定妆图 / 参考图 ----------
    def generate_character_image(self, script):
        """多参考图生成：3 角色定妆图 + 场景图 + 物品图，上传到 ComfyUI input。

        返回 dict：
          {
            "character_all": [input文件名...],   # 全部角色定妆图（按脚本 characters 顺序）
            "scene_map": {场景名: input文件名},
            "prop_map":  {物品名: input文件名},
            "ref_index": {...},  # 见 build_shot_refs
          }
        兼容性：脚本仅有单 "character" 时退化为单角色单图（返回 character_all 只有一张）。
        """
        def _gen_and_upload(prompt_text, prefix, local_name):
            if self.image_backend == "api":
                # NVIDIA FLUX 云端生图 -> 本地 PNG -> 上传 ComfyUI input
                _api_local = os.path.join(self.output_dir, local_name)
                return self._api_image(prompt_text, _api_local, prefix)
            # ---- 本地：本机 ComfyUI Z-Image 文生图 ----
            z_api = generator.build_zimage_prompt(prompt_text, prefix)
            entry = run_and_get_outputs(self.client, z_api)
            fn, sub, typ = find_media(entry)
            if not fn:
                self.log(f"  [!] 生成失败（{prefix}），跳过该参考图")
                return None
            local = os.path.join(self.output_dir, local_name)
            self.client.view_image(fn, sub, typ, save_to=local)
            up = self.client.upload_image(local)
            iname = up.get("name")
            if iname:
                self.log(f"    参考图已上传：input/{iname}")
            return iname

        result = {"character_all": [], "scene_map": {}, "prop_map": {}}
        chars = script.get("characters") or ([{"name": "主角", "prompt": script.get("character", "")}]
                                             if script.get("character") else [])
        chars = [c for c in chars if (c.get("prompt") or "").strip()]
        if not chars:
            raise RuntimeError("剧本缺少 characters / character 字段")

        self.log(f"阶段2/4：生成并上传参考图（{len(chars)} 角色 + 场景 + 物品）…")
        # 角色定妆图统一加"全身站姿 + 服饰清晰"框架，保证 H3 参考图能锁定颜色与外观
        _char_frame = ", full body, standing facing camera, front view, clean background, clear outfit and clothing colors, high detail"
        # 1) 角色定妆图
        for ci, c in enumerate(chars, start=1):
            name = c.get("name", f"角色{ci}")
            prompt_text = c.get("prompt", "").strip()
            if self.args.no_enhance:
                prompt_text = c.get("image_prompt") or prompt_text
            prompt_text = (prompt_text + _char_frame).strip()
            self.log(f"  [角色{ci}/{len(chars)}] {name} 生成定妆图…")
            iname = _gen_and_upload(prompt_text, generator.CHAR_PREFIX, f"character_{ci}.png")
            if iname:
                result["character_all"].append(iname)
            else:
                result["character_all"].append(None)  # 占位，保证索引对齐

        # 2) 场景图：提取所有镜头 scene 去重，各生成一张参考图（带全局风格，锁定场景氛围）
        scenes = _collect_scenes(script)
        g_style = (script.get("style") or "").strip()
        _style_suffix = (" " + g_style) if g_style else ""
        self.log(f"  场景参考图（{len(scenes)} 个场景）…")
        for si, (scene_name, desc) in enumerate(scenes, start=1):
            iname = _gen_and_upload((desc + _style_suffix).strip(), generator.CHAR_PREFIX + f"/scene_{si}",
                                    f"scene_{si}.png")
            if iname:
                result["scene_map"][scene_name] = iname

        # 3) 物品图：提取所有镜头 prop 去重，各生成一张参考图
        props = _collect_props(script)
        self.log(f"  物品参考图（{len(props)} 个物品）…")
        for pi, (prop_name, desc) in enumerate(props, start=1):
            iname = _gen_and_upload(desc, generator.CHAR_PREFIX + f"/prop_{pi}",
                                    f"prop_{pi}.png")
            if iname:
                result["prop_map"][prop_name] = iname

        # 保存参考图映射，供 --skip-images 复用/重传（用户可自行修改图片后继续）
        try:
            with open(os.path.join(self.output_dir, "refs_result.json"), "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return result

    def refs_from_disk(self, script):
        """--skip-images：复用输出目录已有参考图并重新上传到 ComfyUI input。

        参考图生成时会在输出目录保存 refs_result.json（角色/场景/物品 -> input 文件名映射）。
        这里读取该映射，把用户可能修改过的本地图（character_*.png 等）重新上传；
        用户删除/新增的图按文件存在性自适应。返回结构与 generate_character_image 一致。
        """
        import glob as _glob
        map_path = os.path.join(self.output_dir, "refs_result.json")
        saved = {}
        if os.path.isfile(map_path):
            try:
                with open(map_path, "r", encoding="utf-8") as f:
                    saved = json.load(f) or {}
            except Exception:
                saved = {}
        self.log("阶段2/4（复用）：使用输出目录已有参考图并重新上传…")

        def _reup(old_iname, local_name):
            local = os.path.join(self.output_dir, local_name)
            if not os.path.isfile(local):
                return old_iname or None
            try:
                up = self.client.upload_image(local)
                if up.get("name"):
                    self.log(f"    已重新上传：{local_name} -> input/{up['name']}")
                    return up["name"]
            except Exception as e:
                self.log(f"  [!] 上传失败 {local_name}：{e}")
            return old_iname or None

        result = {"character_all": [], "scene_map": {}, "prop_map": {}}
        chars = script.get("characters") or []
        saved_chars = saved.get("character_all") or [None] * len(chars)
        for ci in range(1, len(chars) + 1):
            old = saved_chars[ci - 1] if ci - 1 < len(saved_chars) else None
            result["character_all"].append(_reup(old, f"character_{ci}.png"))
        for mp_key, prefix in (("scene_map", "scene_"), ("prop_map", "prop_")):
            for i, (name, old) in enumerate((saved.get(mp_key) or {}).items(), start=1):
                result[mp_key][name] = _reup(old, f"{prefix}{i}.png")
            if not result[mp_key]:
                for f in sorted(_glob.glob(os.path.join(self.output_dir, prefix + "*.png"))):
                    try:
                        up = self.client.upload_image(f)
                        result[mp_key][os.path.splitext(os.path.basename(f))[0]] = up.get("name")
                    except Exception:
                        pass
        return result

    # ---------- 阶段 3：逐镜头视频 ----------
    def generate_shots(self, script, refs_result):
        shots = script["shots"]
        total = len(shots)
        self.log(f"阶段3/4：逐镜头 H3 ref2va 生成视频（共 {total} 个镜头）…")
        # 视频工作流：默认 dyt.json（--workflow 可覆盖；文件不存在时 generator 回退内置 ref2va）
        from factory import workflow_dyt as _wfd
        wf_path = getattr(self.args, "workflow", None) or _wfd.default_workflow_path()
        if os.path.isfile(wf_path):
            self.log(f"视频工作流：{wf_path}")
        else:
            self.log(f"[warn] 视频工作流不存在（{wf_path}），回退内置 H3 ref2va 节点图")
        params = dict(
            steps=self.args.steps,
            megapixels=self.args.megapixels,
            aspect_ratio=self.args.aspect,
            workflow=wf_path,
            no_rtx=bool(getattr(self.args, "no_rtx_upscale", False)),
        )
        # RTX 超分档位：off=关闭 / 2x=1 个 RTX 2x / 4x=两个 RTX 2x 串联（二次放大省显存）
        up = getattr(self.args, "upscale", None)
        if up:
            params["upscale"] = up
        # MiniMax H3 Latent Upscaler（默认 2.0 启用）：latent 神经网络放大替代 RTX 像素放大，
        # 修复低分辨率生成时的脸部崩坏；--no-latent-upscale 或 --latent-upscale 0 关闭
        lu = float(getattr(self.args, "latent_upscale", 0.0) or 0.0)
        if getattr(self.args, "latent_upscale_off", False):
            lu = 0.0
        if lu > 0:
            params["latent_upscale"] = lu
            if getattr(self.args, "latent_upscale_model", None):
                params["latent_upscale_model"] = self.args.latent_upscale_model
            lu_prec = getattr(self.args, "latent_upscale_precision", "fp16") or "fp16"
            if lu_prec != "fp16":
                params["latent_upscale_precision"] = lu_prec

        if self.args.width and self.args.height:
            params["width"] = self.args.width
            params["height"] = self.args.height
        # MiniMax 六段式/导演台模板 与 对白占比 约束
        mm = getattr(self.args, "minimax_template", None)
        if mm:
            params["minimax_mode"] = mm
            params["total"] = len(shots)
            params["is_first"] = True
        dlg = float(getattr(self.args, "dialogue_ratio", 0.0) or 0.0)
        if dlg > 0:
            params["dialogue_ratio"] = dlg
        # dyt 工作流参考图缩放：match=快 / max=身份保真更强（官方 H3 文档建议 max 增强一致性）
        ris = getattr(self.args, "ref_image_size", None)
        if ris:
            params["ref_image_size"] = ris
        # TTS 配音：启用时提示 H3 弱化原生人声，避免与 TTS 双声冲突
        if getattr(self.args, "tts_enabled", False):
            params["tts_mode"] = True

        done = 0
        for i, shot in enumerate(shots, start=1):
            shot_file = os.path.join(self.shots_dir, f"shot_{i:03d}.mp4")
            if self.args.resume and os.path.isfile(shot_file):
                self.log(f"  [{i}/{total}] 已存在，跳过")
                task_state.save(self.output_dir, phase="shots", done=False,
                                done_shots=done + 1, total_shots=total)
                done += 1
                continue

            duration = float(str(shot.get("duration", "5")).strip() or "5")
            duration = max(8.0, min(15.0, duration))
            shot["duration_sec"] = duration
            # 提示词长度自查：dyt 模式要求 LLM 生成的镜头提示词不少于 500 字（完整剧情/连贯/不崩脸/情绪语气）
            _vp_len = len((shot.get("video_prompt") or "").strip())
            if mm == "dyt" and 0 < _vp_len < 500:
                self.log(f"  [warn] 镜头{i} video_prompt 仅 {_vp_len} 字（要求≥500字），"
                         f"最终提示词将由引擎补足定妆/站位/对白/声景段")
            self.log(f"  [{i}/{total}] 镜头{i} 生成中（{duration}s，{shot.get('scene', '')}）…")

            # 组装本镜头参考图（角色出场 + 场景 + 物品）
            ref_images, refs = _assemble_shot_refs(shot, refs_result)
            shot["refs"] = refs
            # 导演台：首镜不加"无硬切"，后续镜头都加，保证跨镜无缝衔接
            if mm:
                params["is_first"] = (i == 1)
            params["save_prefix"] = generator.SHOT_PREFIX + f"/shot_{i:03d}"
            api = generator.build_shot_video_prompt(shot, ref_images, params)
            t0 = time.time()
            entry = run_and_get_outputs(self.client, api)
            fn, sub, typ = find_media(entry, exts=(".mp4", ".webm", ".mov"))
            if not fn:
                self.log(f"  [!] 镜头{i} 未获取到视频输出，跳过")
                continue
            # 首部废帧：dyt 工作流多生成 17 帧废帧，先下载原片，裁掉前 17 帧再保存，
            # 规避 H3 首段闪烁/黑帧/崩坏（内置 ref2va 路径无废帧，直接保存）
            warm = int(params.get("warmup_frames") or 0)
            if warm > 0:
                raw = shot_file + ".warm.mp4"
                self.client.view_image(fn, sub, typ, save_to=raw)
                if trim_first_frames(raw, shot_file, n=warm, fps=generator.H3_FPS):
                    os.remove(raw)
                else:
                    self.log("  [warn] 裁废帧失败，保留原片（含首部废帧）")
                    os.replace(raw, shot_file)
            else:
                self.client.view_image(fn, sub, typ, save_to=shot_file)
            done += 1
            self.log(f"  [{i}/{total}] 镜头{i} 完成（{time.time() - t0:.0f}s）-> {os.path.basename(shot_file)}")
            task_state.save(self.output_dir, phase="shots", done=False,
                            done_shots=done, total_shots=total)

        self.log(f"  共完成 {done}/{total} 个镜头")
        return sorted([os.path.join(self.shots_dir, f) for f in os.listdir(self.shots_dir)
                       if f.endswith(".mp4")])

    # ---------- 阶段 4：拼接 ----------
    def finalize(self, shot_files, script):
        self.log("阶段4/4：ffmpeg 拼接完整短剧…")
        if not shot_files:
            raise RuntimeError("没有可拼接的镜头")
        title = str(script.get("title", "drama")).strip() or "drama"
        title = re.sub(r'[\\/:*?"<>|\s]+', "_", title)[:40] or "drama"
        # 成片文件名带标题+时间戳（同秒重复时递增后缀），避免新短剧覆盖旧短剧
        ts = time.strftime("%Y%m%d_%H%M%S")
        out = os.path.join(self.output_dir, f"final_drama_{title}_{ts}.mp4")
        _n = 2
        while os.path.exists(out):
            out = os.path.join(self.output_dir, f"final_drama_{title}_{ts}_{_n}.mp4")
            _n += 1
        concat_videos(shot_files, out, reencode=self.args.reencode)
        self.log(f"  完整短剧已生成：{out}")
        # 成片成功：任务状态置 done，不再出现在「继续任务」列表
        task_state.save(self.output_dir, done=True, phase="done",
                        final_video=os.path.basename(out))
        # 同时写一份 final_drama.mp4（最新成片，GUI 定位用），历史版本保留在带时间戳的文件中
        latest = os.path.join(self.output_dir, "final_drama.mp4")
        if os.path.abspath(out) != os.path.abspath(latest):
            try:
                import shutil
                shutil.copy2(out, latest)
            except Exception as e:
                self.log(f"  [warn] 无法写 final_drama.mp4：{e}")
        # 成功成片：未激活状态下扣除一次免费试用
        if not getattr(self.args, "no_license_check", False):
            try:
                from factory import activation
                rem = activation.consume_trial()
                if rem is not None and rem >= 0:
                    self.log(f"  已计入免费试用，剩余 {rem} 次（输入激活码可无限使用）")
            except Exception:
                pass
        return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="短剧工厂：一句话生成完整竖屏短剧")
    ap.add_argument("story", nargs="?", default=None, help="一句话剧情梗概")
    ap.add_argument("--story", dest="story_opt", default=None, help="一句话剧情梗概（--story 形式）")
    ap.add_argument("--url", default="http://127.0.0.1:8188", help="ComfyUI 地址")
    ap.add_argument("--output", default=None, help="输出目录（默认 comfyui-drama/output/<标题>）")
    ap.add_argument("--steps", type=int, default=16, help="H3 采样步数（默认 16）")
    ap.add_argument("--megapixels", type=float, default=0.4, help="H3 分辨率（MP，默认 0.4）")
    ap.add_argument("--aspect", default="9:16 (Portrait Widescreen)", help="H3 画面比例")
    ap.add_argument("--width", type=int, default=None, help="强制宽度（覆盖分辨率计算）")
    ap.add_argument("--height", type=int, default=None, help="强制高度（覆盖分辨率计算）")
    ap.add_argument("--no-enhance", action="store_true", help="跳过定妆图 LLM 增强")
    ap.add_argument("--image-backend", choices=["local", "api"], default="local",
                    help="参考图（角色定妆/场景/物品）生成后端：local=本机 ComfyUI Z-Image（默认）；api=NVIDIA FLUX 云端文生图")
    ap.add_argument("--image-api-config", default=None,
                    help="NVIDIA 生图 API 配置 JSON 路径（image_api.json；不传自动找 exe/工程目录）")
    ap.add_argument("--resume", action="store_true", help="断点续跑（跳过已存在的镜头）")
    ap.add_argument("--reencode", action="store_true", help="拼接时强制重编码（不同分辨率镜头时使用）")
    ap.add_argument("--script-json", default=None, help="直接使用已有剧本 JSON 文件，跳过 LLM 阶段")
    ap.add_argument("--target-seconds", type=int, default=None, help="目标总时长（秒），LLM 据此决定镜头数")
    ap.add_argument("--plan-only", action="store_true", help="只生成剧本并预览（镜头数/总时长/预计耗时），不生成画面")
    ap.add_argument("--llm", default=generator.LLM_DEFAULT,
                    choices=list(generator.LLM_CONFIGS.keys()) + ["custom"],
                    help=f"LLM 模型（默认 {generator.LLM_DEFAULT}）：qwen3.8=27B长输出/慢，qwen3.5=9B快，custom=自定义提供商 API 推理（需 --provider-config）")
    ap.add_argument("--characters-json", default=None,
                    help="预置角色 JSON 文件路径（list[{\"name\",\"prompt\"}]），LLM 只使用不生成")
    ap.add_argument("--provider-config", default=None,
                    help="自定义 OpenAI 兼容提供商配置 JSON（见 factory/provider.py；不传则自动发现 ~/.drama/providers.json 或项目 providers.json）")
    ap.add_argument("--provider", default=None,
                    help="从 provider 配置中按 name 选择具体提供商（缺省取 default 标记或第一个）")
    ap.add_argument("--review", action="store_true",
                    help="剧本生成后 AI 自动审核/修改一次（有自定义提供商走云端，否则用本地 LLM）")
    ap.add_argument("--review-instruction", default=None,
                    help="AI 审核时附加的用户修改要求（与 --review 搭配；交互模式可随时输入）")
    ap.add_argument("--yes", action="store_true",
                    help="跳过剧本预览交互确认，直接生成（批处理/无人值守）")
    ap.add_argument("--no-license-check", action="store_true",
                    help="跳过激活/试用检查（仅供内部调试，勿用于分发版本）")
    ap.add_argument("--minimax-template", default=None,
                    choices=["six_section", "director", "dyt"],
                    help="把逐镜头提示词改写为 MiniMax-H3 六段式/导演台模板（six_section=每镜头六段式；director=六段式+跨幕无硬切衔接，增强连贯性与一致性）")
    ap.add_argument("--dialogue-ratio", type=float, default=0.0,
                    help="对白口播占全片总时长的最低比例（0~1，如 0.6 表示对白≥60%%）；开启后剧本导演/分幕扩写会强制对白密度，并在剧本生成后校验")
    ap.add_argument("--ref-image-size", choices=["match", "max"], default=None,
                    help="dyt 工作流参考图缩放：match=快（默认），max=保留2048px短边、身份与服饰颜色一致性更强（官方建议，稍慢）")
    ap.add_argument("--workflow", default=None,
                    help="视频生成用的 ComfyUI 工作流 JSON 路径（缺省自动使用 dyt.json；文件不存在时回退内置 ref2va 节点图）")
    ap.add_argument("--no-rtx-upscale", action="store_true",
                    help="视频生成时移除 dyt.json 中的 RTX 超分节点（等价 --upscale off；显存紧张或非 RTX 显卡时使用）")
    ap.add_argument("--upscale", choices=["off", "2x", "4x"], default=None,
                    help="RTX 超分：off=关闭（移除 dyt.json 的 RTX 节点）；2x=调用 1 个 RTX 2x 放大；"
                         "4x=调用 dyt.json 两个 RTX 2x 节点串联（二次放大，避免一次 4x 崩显存）。"
                         "默认不干预（保留工作流内 RTX）")
    ap.add_argument("--latent-upscale", type=float, default=0.0, metavar="N",
                    help="MiniMax H3 Latent Upscaler 空间放大倍数（默认关闭；16GB 显存跑 H3 视频请保持关闭，显存充裕可开 2.0）：低清 latent 用专用 3D "
                         "神经网络放大后再解码，替代 RTX 像素放大，修复低分辨率生成时的脸部崩坏；"
                         "0 或 --no-latent-upscale 关闭")
    ap.add_argument("--no-latent-upscale", dest="latent_upscale_off", action="store_true",
                    help="关闭 Latent Upscaler（保持 RTX 像素放大链路）")
    ap.add_argument("--latent-upscale-model", default=None,
                    help="upscaler 权重文件名（默认 minimax_h3_latent_upscaler_3d_fp16.safetensors，"
                         "放在 ComfyUI/models/latent_upscale_models/）")
    ap.add_argument("--latent-upscale-precision", choices=["fp16", "bf16", "fp32"], default="fp16",
                    help="upscaler 推理精度（默认 fp16；显存紧张可换 bf16）")
    ap.add_argument("--images-only", action="store_true",
                    help="只生成角色/场景/物品参考图并上传，随后退出（不生成视频）")
    ap.add_argument("--skip-images", action="store_true",
                    help="跳过参考图生成，直接复用输出目录中已有的 character_*/scene_*/prop_*.png 生成视频")
    ap.add_argument('--genre', default=None,  
                    choices=toonflow_skills.available_genres(),  
                    help='Story genre key or Chinese name; injects genre director constraints.')  
    ap.add_argument('--art-style', dest='art_style', default=None,  
                    choices=toonflow_skills.available_styles(),  
                    help='Art style key or Chinese name; injects art character/scene/prop constraints.')
    # ---- TTS 配音（角色音色一致）：默认关闭，--tts 开启（--no-tts 兼容保留） ----
    tts_grp = ap.add_mutually_exclusive_group()
    tts_grp.add_argument("--tts", dest="tts_enabled", action="store_true", default=False,
                         help="开启 TTS 角色配音（默认关闭：每个角色绑定固定音色，整剧音色一致；需要联网调用微软 edge-tts）")
    tts_grp.add_argument("--no-tts", dest="tts_enabled", action="store_false",
                         help="（兼容旧参数）关闭 TTS 配音")
    ap.add_argument("--voice-map", default=None,
                    help="角色音色映射 JSON 路径（dict{角色名: 音色ShortName}），覆盖自动音色分配；音色见 edge-tts zh-CN 列表（zh-CN-XiaoxiaoNeural 等）")
  
    args = ap.parse_args(argv) 

    story = args.story or args.story_opt
    if not story and not args.script_json:
        ap.error("请提供一句话剧情梗概，或 --script-json 指定已有剧本")

    # ---- 激活 / 试用门禁（默认启用；plan-only 规划不门禁）----
    if not args.no_license_check and not args.plan_only:
        from factory import activation
        if not activation.has_trial():
            raise RuntimeError(
                "免费试用次数已用完（2/2），且未激活。\n"
                "请先输入有效激活码激活后继续使用。"
            )

    client = ComfyClient(base_url=args.url)
    h = client.health()
    # 剧本阶段可选的远程提供商：配置了才允许 plan-only 在无 ComfyUI 时降级
    has_provider = False
    try:
        from factory import provider as _prov
        has_provider = _prov.pick_provider(
            name=getattr(args, "provider", None),
            path=getattr(args, "provider_config", None)) is not None
    except Exception:
        has_provider = False
    # --script-json + --plan-only：剧本已存在且只需预览，任何情况下都不需要 ComfyUI
    offline_ok = args.plan_only and (has_provider or args.script_json)
    if "error" in h or "comfyui_version" not in h:
        if offline_ok:
            # 只出剧本/预览，不需要本机 ComfyUI，降级为警告继续
            print(f"[警告] ComfyUI 未连接（{args.url}）：{h}")
            print("[警告] 当前为剧本/预览模式，可离线完成（画面生成阶段仍需 ComfyUI）")
        else:
            raise RuntimeError(f"无法连接 ComfyUI（{args.url}）：{h}")

    # 确定输出目录
    if args.output:
        output_dir = args.output
    else:
        output_dir = os.path.join(DEFAULT_OUTPUT_ROOT, time.strftime("%Y%m%d_%H%M%S"))
    os.makedirs(output_dir, exist_ok=True)

    factory = DramaFactory(client, output_dir, args)
    factory.log(f"短剧工厂启动，输出目录：{output_dir}")
    # ---- 任务状态：意外中断保留（继续任务）——plan-only 预览不记状态 ----
    if not args.plan_only:
        _snap = {}
        for _k in ("target_seconds", "llm", "megapixels", "steps", "aspect", "characters_json",
                   "provider_config", "provider", "minimax_template", "dialogue_ratio", "upscale",
                   "image_backend", "image_api_config", "ref_image_size", "workflow",
                   "tts_enabled", "voice_map", "genre", "art_style", "reencode", "width",
                   "height", "no_enhance", "story", "story_opt"):
            _v = getattr(args, _k, None)
            if _v is not None:
                try:
                    json.dumps(_v)
                    _snap[_k] = _v
                except Exception:
                    _snap[_k] = str(_v)
        if story:
            _snap["story"] = story
        task_state.save(output_dir, done=False,
                        phase="refs" if args.script_json else "script",
                        title="", total_shots=0, done_shots=0, params=_snap)

    # 预置角色：--characters-json 提供的优先；否则看剧本顶层 characters
    chars = None
    if args.characters_json and os.path.isfile(args.characters_json):
        with open(args.characters_json, "r", encoding="utf-8") as f:
            chars = json.load(f)
        if not isinstance(chars, list):
            chars = None

    if args.script_json:
        with open(args.script_json, "r", encoding="utf-8") as f:
            script = json.load(f)
        if chars and not script.get("characters"):
            script["characters"] = chars
    else:
        script = factory.generate_script(story, chars)

    # ---- 剧本预览 + 用户审查（可跳过后继续；--plan-only 只预览） ----
    script, _ = _enforce_char_count(script, log=factory.log)
    if not args.plan_only:
        # 剧本就绪：补写 script.json + 更新任务状态（标题/镜头数），供意外中断后续跑
        try:
            with open(os.path.join(output_dir, "script.json"), "w", encoding="utf-8") as f:
                json.dump(script, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        task_state.save(output_dir, done=False, phase="refs",
                        title=str(script.get("title") or ""),
                        total_shots=len(script.get("shots") or []))

    # ---- 对白占比校验（--dialogue-ratio）：生成后校验，不达标则提示 + 自动建议 ----
    dlg_target = float(getattr(args, "dialogue_ratio", 0.0) or 0.0)
    if dlg_target > 0:
        try:
            from factory import minimax_prompt as _mmp
            ok, ratio, msg = _mmp.validate_dialogue_ratio(script, target=dlg_target, log=factory.log)
            factory.log(f"[对白占比] {msg}")
        except Exception as e:
            factory.log(f"[对白占比] 校验跳过：{e}")

    def _show_preview(s):
        n = len(s.get("shots", []))
        total = sum(float(str(x.get("duration", "5")).strip() or 5) for x in s.get("shots", []))
        factory.log(f"[预览] 剧本《{s.get('title')}》 {n} 镜头 / 总时长 {total:.0f}s（目标 {args.target_seconds or '不限'}s）")
        chs = s.get("characters") or []
        factory.log(f"[预览] 角色 {len(chs)} 个：{'、'.join(c.get('name','') for c in chs)}")
        for x in s.get("shots", []):
            factory.log(f"  shot {x.get('shot'):>3} | {str(x.get('duration')):>3}s | {x.get('scene', '')}")
        factory.log(f"[预览] 剧本已保存：{os.path.join(output_dir, 'script.json')}")
        with open(os.path.join(output_dir, "script.json"), "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=2)

    if args.plan_only:
        _show_preview(script)
        return

    # AI 审核/修改：--review 自动执行一次，或在交互中用户要求时执行
    def _ai_review(s, instruction=""):
        if factory.provider is None:
            factory.log(f"[i] 未配置自定义提供商，使用本地 LLM（{factory.llm}）进行 AI 审核…")
            try:
                new_script, raw = factory.review_local(s, instruction)
                if not new_script or "shots" not in new_script:
                    factory.log("[!] 本地 AI 审核未返回有效剧本，保留原剧本")
                    with open(os.path.join(output_dir, "ai_review_raw.txt"), "w", encoding="utf-8") as f:
                        f.write(raw or "")
                    return s
                new_script, _ = _enforce_char_count(new_script, log=factory.log)
                new_script["title"] = new_script.get("title") or s.get("title")
                factory.log(f"  本地 AI 审核完成：{len(new_script.get('shots', []))} 镜头")
                return new_script
            except Exception as e:
                factory.log(f"[!] 本地 AI 审核失败：{e}；保留原剧本")
                return s
        factory.log(f"  AI 审核中（{factory.provider.chat_model}）…")
        try:
            new_script, raw = factory.provider.review_script(s, instruction)
            if not new_script or "shots" not in new_script:
                factory.log("[!] AI 审核未返回有效剧本，保留原剧本")
                with open(os.path.join(output_dir, "ai_review_raw.txt"), "w", encoding="utf-8") as f:
                    f.write(raw or "")
                return s
            new_script, _ = _enforce_char_count(new_script, log=factory.log)
            new_script["title"] = new_script.get("title") or s.get("title")
            factory.log(f"  AI 审核完成：{len(new_script.get('shots', []))} 镜头")
            return new_script
        except Exception as e:
            factory.log(f"[!] AI 审核失败：{e}；保留原剧本")
            return s

    if args.review:
        script = _ai_review(script, args.review_instruction or "")
        _show_preview(script)

    def _interactive_choice(prompt, timeout=60):
        """Windows 非阻塞按键等待：60 秒内无输入自动返回""（= 接受并继续）。
        仅在真控制台可用；stdin 非交互（如 GUI 子进程）时回退普通 input()。
        """
        try:
            import msvcrt
            if not msvcrt.isatty(0):
                raise OSError("not a console")
        except Exception:
            return input(prompt).strip().lower()
        sys.stdout.write(prompt)
        sys.stdout.flush()
        deadline = time.time() + timeout
        while True:
            if time.time() >= deadline:
                sys.stdout.write("\n")
                sys.stdout.flush()
                factory.log(f"[{timeout} 秒内无操作，自动接受剧本并继续生成]")
                return ""
            try:
                if msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    if ch in ("\r", "\n"):
                        sys.stdout.write("\n"); sys.stdout.flush()
                        return ""
                    low = ch.lower()
                    if low in ("r", "e", "q"):
                        sys.stdout.write(ch + "\n"); sys.stdout.flush()
                        return low
                    if ch == "\x03":
                        raise KeyboardInterrupt
            except OSError:
                return input(prompt).strip().lower()
            time.sleep(0.2)

    if not args.yes:
        # 交互确认：接受 / AI 审核 / 附加要求修改 / 退出（60 秒无操作自动接受）
        while True:
            try:
                ans = _interactive_choice(f"\n请审查剧本（{output_dir}）："
                                          f"[回车]接受并继续生成  [r]AI审核修改  [e]输入修改要求  [q]退出\n> ")
            except EOFError:
                ans = ""
            except KeyboardInterrupt:
                factory.log("用户中止，剧本已保留，退出")
                return
            if ans in ("", "a", "y", "yes", "accept"):
                break
            if ans in ("q", "quit", "exit", "x"):
                factory.log("用户中止，剧本已保留，退出")
                return
            if ans == "r":
                script = _ai_review(script)
                _show_preview(script)
                continue
            if ans == "e":
                try:
                    inst = input("请输入修改要求（自然语言）：\n> ").strip()
                except EOFError:
                    inst = ""
                if inst:
                    script = _ai_review(script, inst)
                    _show_preview(script)
                continue
            factory.log("输入无效，请输入 回车/r/e/q")

    # 注入角色列表到每个 shot，供 _assemble_shot_refs 按名字定位角色图
    chars = script.get("characters")
    if chars:
        for s in script.get("shots", []):
            s["_script_chars"] = chars
    # 注入整份剧本上下文（角色/场景/物品/风格）到每个 shot，供六段式模板重组时引用
    factory._attach_script_to_shots(script)

    if args.images_only:
        refs_result = factory.generate_character_image(script)
        factory.log(f"阶段2完成：参考图已生成并上传，输出目录：{output_dir}")
        task_state.save(output_dir, done=False, phase="images_ready")
        return None
    refs_result = (factory.refs_from_disk(script)
                   if args.skip_images else factory.generate_character_image(script))
    task_state.save(output_dir, done=False, phase="shots")
    shot_files = factory.generate_shots(script, refs_result)
    # TTS 配音：每个角色绑定固定音色，整剧音色一致（默认关闭；--tts 开启）
    if getattr(args, "tts_enabled", False):
        factory.log("阶段3.5：TTS 角色配音（edge-tts，整剧音色一致）…")
        voice_map = {}
        vmp = getattr(args, "voice_map", None)
        if vmp and os.path.isfile(vmp):
            with open(vmp, "r", encoding="utf-8") as _f:
                voice_map = json.load(_f) or {}
        try:
            from factory import tts as _tts
            _ok, _fail, _voices = _tts.synthesize_script(
                script, factory.shots_dir, output_dir=factory.output_dir,
                voice_map=voice_map, log=factory.log)
            factory.log(f"[TTS] 配音完成 {_ok} 镜头，失败 {_fail}") if _ok or _fail else None
        except Exception as _e:
            factory.log(f"[!] TTS 配音失败（不影响成片，可后续补配）：{_e}")
    task_state.save(output_dir, done=False, phase="concat")
    final = factory.finalize(shot_files, script)
    factory.log(f"完成！完整短剧：{final}")
    return final


if __name__ == "__main__":
    main()
