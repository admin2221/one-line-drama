# -*- coding: utf-8 -*-
"""短剧生成器 · 图形界面（tkinter）
版本 v2：重排布局 + 开机自检 + 2次免费试用 + 激活码机制。

功能：
- 故事/参数分区、日志区、底部状态栏分区清晰
- 启动时自动检查本机 ComfyUI 是否在线（自检）
- 未激活：免费试用 2 次（成功成片扣一次）；用完须输入激活码
- 已激活：无限使用
"""
import os
import re
import time
import subprocess
import sys
import threading
import urllib.request
import urllib.error
import json

import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox, scrolledtext, simpledialog

# 打包成 windowed（无控制台）时 stdout 可能为 None，需防御；并把未处理异常记入日志便于排查
try:
    if sys.stdout is not None:
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_ERR_LOG = os.path.join(os.environ.get("LOCALAPPDATA", r"C:\Windows\Temp"),
                        "DramaShorts", "drama_gui_error.log")
_orig_hook = sys.excepthook
def _excepthook(tp, val, tb):
    import traceback
    try:
        os.makedirs(os.path.dirname(_ERR_LOG), exist_ok=True)
        with open(_ERR_LOG, "a", encoding="utf-8") as f:
            f.write("".join(traceback.format_exception(tp, val, tb)) + "\n")
    except Exception:
        pass
    if _orig_hook is not None:
        _orig_hook(tp, val, tb)
sys.excepthook = _excepthook

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from factory import task_state  # 任务状态（意外中断保留 / 继续任务）

ENGINE_NAMES = ["drama-cli.exe", "drama-cli-onefile.exe", "drama-cli"]
DEFAULT_COMFY = "http://127.0.0.1:8188"
TRIAL_LIMIT = 2
PURCHASE_URL = "https://www.goofish.com/item?id=1078783056478"
APP_TITLE = "短剧生成器 · Drama Shorts Generator（v2）"
# NVIDIA FLUX 云端生图默认端点（可在“生图API设置…”中修改，key 存 exe 旁 image_api.json）
IMGAPI_DEFAULT_ENDPOINT = "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.2-klein-4b"


# ---------------- 剧本审查：JSON 展示与翻译辅助（模块级，便于复用） ----------------
def _script_pretty_json(script):
    """把剧本转成可读的分镜 JSON 文本（含格式化后的完整 shots）。"""
    try:
        return json.dumps(script, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "shots": script.get("shots", [])},
                          ensure_ascii=False, indent=2)


def _script_english_blocks(script):
    """提取剧本中需要翻译成中文的英文字段，返回 [{key,label,text}]。"""
    blocks = []

    def add(key, label, text):
        t = (text or "").strip()
        if not t:
            return
        # 含较多中文的字段视为已本地化，不请求翻译
        if sum('\u4e00' <= ch <= '\u9fff' for ch in t) >= len(t) / 2:
            return
        blocks.append({"key": key, "label": label, "text": t})

    title = (script.get("title") or "").strip()
    if title:
        add("title", "标题 (title)", title)
    style = (script.get("style") or "").strip()
    if style:
        add("style", "全局风格 (style)", style)
    for i, c in enumerate(script.get("characters") or []):
        add(f"char_{i}", f"角色[{c.get('name','') or i}]定妆 (prompt)", c.get("prompt", ""))
    for s in script.get("shots") or []:
        sh = str(s.get("shot", "?"))
        for fld in ("image_prompt", "video_prompt", "transition_prev"):
            label = {"image_prompt": "画面提示词", "video_prompt": "运镜提示词",
                     "transition_prev": "衔接说明"}.get(fld, fld)
            add(f"shot_{sh}_{fld}", f"镜头{sh} · {label} ({fld})", s.get(fld, ""))
    return blocks


# ---------------- 翻译技能：专业影视/短剧提示词翻译（云端/本地共用） ----------------
_TRANS_SYSTEM = (
    "你是资深影视翻译专家，专精 AI 短剧分镜提示词与剧本的英译中，"
    "精通镜头语言、影视美术术语与短剧台词的行业标准译法。"
)

_TRANS_SKILLS = (
    "翻译技能与硬性规则：\n"
    "1.【镜头语言】运镜/景别用行业标准译法：close-up→特写、medium shot→中景、"
    "wide/long shot→全景、extreme close-up→大特写、dolly in→推镜、dolly out→拉镜、"
    "pan→横摇、tilt→纵摇、tracking/follow shot→跟拍、POV→第一人称视角、"
    "low angle→仰拍、high angle→俯拍、over-the-shoulder→过肩镜头、slow motion→慢动作；\n"
    "2.【台词口语化】dialogue 类译文符合角色身份、年龄与口语习惯，保留语气、情绪和潜台词，拒绝翻译腔；\n"
    "3.【译名一致】同一角色名、场景名、道具名全片统一译名，符合中文短剧命名习惯；\n"
    "4.【技术结构原样保留】<Picture N>、[img_N] 等标签、(0-5s) 等时段标记、"
    "画幅比/分辨率/帧率等技术参数一律不译；\n"
    "5.【语义零遗漏】光影、服饰、表情、场景、氛围等细节必须全部保留，禁止概括缩写；\n"
    "6.【表达地道】按中文习惯断句，避免欧化长句；独特风格词可音译并在括号内附原词。\n"
    "输出要求：严格只输出一个 JSON 对象，键为每条左侧标识（key），值为对应中文翻译，不要任何其他文字。"
)


def _trans_user_prompt(blocks):
    items = "\n".join(f'- {b["key"]}: {b["text"]}' for b in blocks)
    return ("请把以下 AI 短剧分镜提示词逐条翻译成中文（条目数：" + str(len(blocks)) + "）：\n\n"
            + items + "\n\n" + _TRANS_SKILLS)


def _parse_trans_json(text, blocks):
    """从 LLM 输出提取 {key: 译文}；括号配平解析，容忍前后杂文。失败返回 None。"""
    if not text:
        return None
    data = None
    try:
        from factory.agent import _extract_json
        data = _extract_json(text)
    except Exception:
        data = None
    if data is None:
        import re as _re
        m = _re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                data = json.loads(m.group(0))
            except Exception:
                data = None
    if not isinstance(data, dict):
        return None
    return {str(k): str(v) for k, v in data.items()}


def _translate_batch(call, blocks, chunk=6):
    """分批调用 LLM 翻译；单批解析失败/缺键时自动二分重试，长剧本不因输出截断而失败。"""
    if not blocks:
        return {}
    if len(blocks) == 1:
        mapping = _parse_trans_json(call(_trans_user_prompt(blocks)), blocks) or {}
        mapping.setdefault(blocks[0]["key"], "")
        return mapping
    if len(blocks) > chunk:
        out = {}
        for i in range(0, len(blocks), chunk):
            out.update(_translate_batch(call, blocks[i:i + chunk], chunk))
        return out
    mapping = _parse_trans_json(call(_trans_user_prompt(blocks)), blocks)
    if mapping is not None and all(b["key"] in mapping for b in blocks):
        return mapping
    mid = len(blocks) // 2
    out = _translate_batch(call, blocks[:mid], chunk)
    out.update(_translate_batch(call, blocks[mid:], chunk))
    return out


def _translate_blocks_via_provider(cfg_path, blocks):
    """用已配置的 OpenAI 兼容提供商批量翻译（专业影视翻译技能提示词），返回 {key: 译文}。"""
    if not blocks:
        return {}
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from factory.provider import load_providers, ProviderClient
    cfg = load_providers(cfg_path)
    if not cfg:
        raise RuntimeError("提供商的配置文件为空")
    client = ProviderClient(cfg[0])

    def _call(prompt):
        return client.chat(_TRANS_SYSTEM, prompt, temperature=0.2, max_tokens=4096)

    return _translate_batch(_call, blocks)


def _translate_blocks_via_local(cfg_path, blocks, llm="qwen3.5", comfy_url=DEFAULT_COMFY):
    """用本机 LLM（走 ComfyUI llama 节点）批量翻译，与云端共用同一专业翻译技能提示词。"""
    if not blocks:
        return {}
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        from factory.client import ComfyClient
        from factory.generator import build_script_prompt
        from factory.drama_factory import run_and_get_text
    except Exception as e:
        raise RuntimeError(f"本地翻译依赖加载失败：{e}")

    # 本地 LLM 走 ComfyUI llama 节点（与剧本生成同一后端）
    client = ComfyClient(comfy_url)
    if not client.health():
        raise RuntimeError("本地翻译需要 ComfyUI 在线（127.0.0.1:8188），当前未连接。")

    def _call(prompt):
        api = build_script_prompt(prompt, _TRANS_SYSTEM, max_tokens=2048,
                                  temperature=0.2, llm=llm)
        return run_and_get_text(client, api)

    return _translate_batch(_call, blocks)


# 内置角色模板目录（presets 下每个 json 为一套可选的角色定妆）。
# 源码：<项目>/characters/presets；打包后：<sys._MEIPASS>/characters/presets
_BUNDLE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PRESETS_DIR = os.path.join(_BUNDLE_DIR, "characters", "presets")
if not os.path.isdir(PRESETS_DIR):
    # 宽松兜底：exe 同目录下也可以放置 presets 供用户自定义
    PRESETS_DIR = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0] or __file__)), "presets")

# 可用的剧本 LLM 配置（同步自 factory/generator）。GUI 只取 key 列表 + 默认值。
try:
    from factory.generator import LLM_CONFIGS, LLM_DEFAULT
    _LLM_KEYS = list(LLM_CONFIGS.keys())
except Exception:
    LLM_CONFIGS = {}
    LLM_DEFAULT = "qwen3.8"
    _LLM_KEYS = ["qwen3.5", "qwen3.8"]
# 分辨率/Aspect 方向选择
ASPECT_OPTIONS = [
    "9:16 (Portrait Widescreen) 竖屏",
    "16:9 (Widescreen) 横屏",
    "1:1 (Square) 方形",
    "4:3 (Standard) 4:3",
    "3:4 (Portrait) 3:4",
]
ASPECT_MAP = {
    "9:16 (Portrait Widescreen) 竖屏": "9:16 (Portrait Widescreen)",
    "16:9 (Widescreen) 横屏": "16:9 (Widescreen)",
    "1:1 (Square) 方形": "1:1 (Square)",
    "4:3 (Standard) 4:3": "4:3 (Standard)",
    "3:4 (Portrait) 3:4": "3:4 (Portrait)",
}


# ---------------- MP → 分辨率联动（复刻官方 ResolutionSelector 公式：MP×1024² → sqrt → round/×32） ----------------
def _mp_resolution(mp, w_ratio=16, h_ratio=9, multiple=32):
    """按官方 ResolutionSelector 公式把百万像素换算为宽高（×32 对齐）。非法输入返回 None。"""
    try:
        mp = float(str(mp).strip())
    except (TypeError, ValueError):
        return None
    if mp <= 0 or mp > 16:
        return None
    scale = (mp * 1024 * 1024 / (w_ratio * h_ratio)) ** 0.5
    w = int(round(w_ratio * scale / multiple)) * multiple
    h = int(round(h_ratio * scale / multiple)) * multiple
    return w, h


def _mp_hint(mp):
    """生成 MP 输入框旁的动态提示：横屏/竖屏分辨率对照。"""
    r = _mp_resolution(mp)
    if r is None:
        return "如 0.2=608×352 横屏 / 352×608 竖屏"
    w, h = r
    label = str(mp).strip()  # 展示用户输入原样（如 0.4 / 1.0 / 0.20）
    return f"{label}={w}×{h} 横屏 / {h}×{w} 竖屏"


def open_url(url):
    """用默认浏览器打开链接。"""
    try:
        import webbrowser
        webbrowser.open(url)
        return True
    except Exception:
        return False


def _app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def find_engine():
    app_dir = _app_dir()
    for base in (app_dir, os.path.dirname(app_dir), os.getcwd()):
        for name in ENGINE_NAMES:
            p = os.path.join(base, name)
            if os.path.isfile(p):
                return p
    return None


def comfy_health(url=DEFAULT_COMFY):
    """自检 ComfyUI，返回 (ok, msg)。"""
    try:
        with urllib.request.urlopen(url + "/system_stats", timeout=4) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        vram = data.get("devices", [{}])[0].get("vram_total", 0)
        gb = vram / 1024 ** 3
        return True, f"ComfyUI 在线（VRAM 约 {gb:.1f} GB）"
    except Exception as e:
        return False, f"ComfyUI 未在线：{type(e).__name__}"


class DramaGUI(tk.Tk):
    def __init__(self):
        self._enable_dpi_awareness()
        super().__init__()
        self.title("短剧生成器 · Drama Shorts Generator（v2）")
        self.geometry("780x760")
        self.minsize(700, 660)
        self.proc = None
        self.engine_path = find_engine()
        self.comfy_ok = False

        self._load_activation_state()
        self._build_ui()
        self.after(200, self._startup_check)

    @staticmethod
    def _enable_dpi_awareness():
        """Windows 高分屏下让 tkinter 正确缩放，避免窗口过小/模糊。"""
        try:
            import ctypes
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(1)  # system DPI aware
            except Exception:
                ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


    # ---------------- 激活/试用状态 ----------------
    def _load_activation_state(self):
        try:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from factory import activation
            self.activation = activation
        except Exception as e:
            self.activation = None
        self.activated = bool(self.activation and self._act().is_activated())
        self.used = int(self._act().used_trials()) if self.activation else 0

    def _act(self):
        return self.activation if self.activation else _NullActivation()

    # ---------------- 界面 ----------------
    def _build_ui(self):
        # 顶部状态栏（自检）
        self.status_bar = tk.Frame(self, bg="#eceff1", bd=1, relief="sunken")
        self.status_bar.pack(fill="x", side="top")
        self.comfy_st = tk.Label(self.status_bar, text="⏳ 正在自检……", fg="#333", bg="#eceff1",
                                 font=("Microsoft YaHei", 9))
        self.comfy_st.pack(side="left", padx=10, pady=3)
        self.movie_st = tk.Label(self.status_bar, text="", fg="#888", bg="#eceff1",
                                 font=("Microsoft YaHei", 9))
        self.movie_st.pack(side="right", padx=10)

        pad = dict(padx=10, pady=5)
        main = tk.Frame(self); main.pack(fill="both", expand=True, padx=12, pady=6)

        # --- 分区一：故事梗概 ---
        sec1 = tk.LabelFrame(main, text=" 1 · 故事梗概（一句话或一段，含开局钩子/反转/结局）",
                             font=("Microsoft YaHei", 9, "bold"), padx=8, pady=6)
        sec1.pack(fill="x", **pad)
        self.story_txt = scrolledtext.ScrolledText(sec1, height=5, wrap="word",
                                                   font=("Microsoft YaHei", 10))
        self.story_txt.pack(fill="x")

        # --- 分区二：参数 ---
        sec2 = tk.LabelFrame(main, text=" 2 · 生成参数 ", font=("Microsoft YaHei", 9, "bold"),
                             padx=8, pady=6)
        sec2.pack(fill="x", **pad)
        grid = tk.Frame(sec2); grid.pack(fill="x")
        grid.columnconfigure(1, weight=1); grid.columnconfigure(3, weight=1)
        tk.Label(grid, text="总时长(秒)", font=("Microsoft YaHei", 9)).grid(row=0, column=0, sticky="w", pady=2)
        self.dur = tk.Entry(grid, width=8); self.dur.insert(0, "300")
        self.dur.grid(row=0, column=1, sticky="w", pady=2)
        tk.Label(grid, text="3~15分钟≈180~900秒", fg="gray", font=("Microsoft YaHei", 8)).grid(row=0, column=2, sticky="w", padx=8)

        tk.Label(grid, text="分辨率(MP)", font=("Microsoft YaHei", 9)).grid(row=1, column=0, sticky="w")
        self.mp = tk.Entry(grid, width=8); self.mp.insert(0, "0.2")
        self.mp.grid(row=1, column=1, sticky="w")
        self.mp_hint_lb = tk.Label(grid, text=_mp_hint("0.2"), fg="gray", font=("Microsoft YaHei", 8))
        self.mp_hint_lb.grid(row=1, column=2, sticky="w", padx=8)
        # MP 数值变化 → 实时联动右侧横屏/竖屏分辨率示意
        self.mp.bind("<KeyRelease>", lambda _e: self.mp_hint_lb.config(text=_mp_hint(self.mp.get())))
        self.mp.bind("<FocusOut>", lambda _e: self.mp_hint_lb.config(text=_mp_hint(self.mp.get())))

        tk.Label(grid, text="采样步数", font=("Microsoft YaHei", 9)).grid(row=2, column=0, sticky="w")
        self.steps = tk.Entry(grid, width=8); self.steps.insert(0, "16")
        self.steps.grid(row=2, column=1, sticky="w")

        # 画面方向：竖屏 / 横屏 自由切换
        tk.Label(grid, text="画面方向", font=("Microsoft YaHei", 9)).grid(row=3, column=0, sticky="w")
        self.aspect_var = tk.StringVar(value=ASPECT_OPTIONS[0])
        self.aspect_cb = ttk.Combobox(grid, textvariable=self.aspect_var, state="readonly",
                                      values=ASPECT_OPTIONS, width=38, font=("Microsoft YaHei", 9))
        self.aspect_cb.grid(row=3, column=1, columnspan=3, sticky="w", pady=2)

        # 智能体运行方式：仅使用自定义 OpenAI 兼容提供商（已移除本机 LLM 选项）
        self.agent_mode = tk.StringVar(value="cloud")
        agent_row = tk.Frame(sec2); agent_row.pack(fill="x", pady=(4, 0))
        tk.Label(agent_row, text="智能体运行：", font=("Microsoft YaHei", 9)).pack(side="left")
        tk.Radiobutton(agent_row, text="云端（自定义 OpenAI 接口）", variable=self.agent_mode, value="cloud",
                       command=self._agent_mode_toggle, font=("Microsoft YaHei", 9)).pack(side="left")
        self.agent_st = tk.Label(agent_row, text="", fg="#888", font=("Microsoft YaHei", 8))
        self.agent_st.pack(side="left")

        llm_row = tk.Frame(sec2); llm_row.pack(fill="x", pady=(4, 0))
        # 剧本 LLM 总开关：关闭后本地推理（qwen3.5/3.8/3.8A）全部不可用，仅走自定义提供商 API
        self.llm_local_sw = tk.BooleanVar(value=True)
        tk.Checkbutton(llm_row, text="启用本地推理", variable=self.llm_local_sw,
                       command=self._llm_local_sw_toggle, font=("Microsoft YaHei", 9)).pack(side="left")
        tk.Label(llm_row, text="剧本 LLM：", font=("Microsoft YaHei", 9)).pack(side="left")
        self.llm = tk.StringVar(value=LLM_DEFAULT)
        # 从 generator.LLM_CONFIGS 动态生成可选 LLM（含 Aggressive 扩写版）
        llm_labels = {
            "qwen3.5": "qwen3.5(快·带视觉)",
            "qwen3.8": "qwen3.8(27B)",
            "qwen3.8ag": "qwen3.8A(扩写·激进芯)",
            "custom": "自定义模型(API推理接口)",
        }
        self._llm_local_rbs = []
        for key, label in llm_labels.items():
            if key != "custom" and key not in _LLM_KEYS:
                continue
            cmd = self._llm_custom_changed if key == "custom" else None
            rb = tk.Radiobutton(llm_row, text=label, variable=self.llm, value=key,
                                command=cmd, font=("Microsoft YaHei", 9))
            rb.pack(side="left")
            if key != "custom":
                self._llm_local_rbs.append(rb)        # 自定义提供商（OpenAI 兼容推理后端，仅用于剧本；图片/视频仍走本地 ComfyUI）
        self.provider_cfg_path = os.path.join(
            os.path.dirname(os.path.abspath(sys.argv[0] or __file__)), "providers.json")
        prov_row = tk.Frame(sec2); prov_row.pack(fill="x", pady=(2, 0))
        self.use_provider = tk.BooleanVar(value=os.path.isfile(self.provider_cfg_path))
        tk.Checkbutton(prov_row, text="使用自定义提供商（剧本推理走远程 API，图片/视频仍用本地 ComfyUI）",
                       variable=self.use_provider, font=("Microsoft YaHei", 9),
                       command=self._provider_toggle).pack(side="left")
        tk.Button(prov_row, text="提供商设置…", command=self._provider_settings,
                  font=("Microsoft YaHei", 9)).pack(side="left", padx=6)
        self.provider_st = tk.Label(prov_row, text="", fg="#888", font=("Microsoft YaHei", 8))
        self.provider_st.pack(side="left")
        self._refresh_provider_st()

        # --- 参考图（角色/场景/物品）生图后端：本地 ComfyUI Z-Image / NVIDIA FLUX 云端 API ---
        self.imgapi_cfg_path = os.path.join(
            os.path.dirname(os.path.abspath(sys.argv[0] or __file__)), "image_api.json")
        img_row = tk.Frame(sec2); img_row.pack(fill="x", pady=(2, 0))
        self.image_backend = tk.StringVar(value="local")
        tk.Label(img_row, text="生图方式：", font=("Microsoft YaHei", 9)).pack(side="left")
        tk.Radiobutton(img_row, text="本地（ComfyUI Z-Image）", variable=self.image_backend,
                       value="local", font=("Microsoft YaHei", 9)).pack(side="left")
        tk.Radiobutton(img_row, text="云端（NVIDIA FLUX API）", variable=self.image_backend,
                       value="api", font=("Microsoft YaHei", 9)).pack(side="left", padx=4)
        tk.Button(img_row, text="生图API设置…", command=self._imgapi_settings,
                  font=("Microsoft YaHei", 9)).pack(side="left", padx=4)
        self.imgapi_st = tk.Label(img_row, text="", fg="#888", font=("Microsoft YaHei", 8))
        self.imgapi_st.pack(side="left")
        self._refresh_imgapi_st()

        # --- MiniMax 六段式模板 + 对白占比（增强连贯性/一致性） ---
        mm_row = tk.Frame(sec2); mm_row.pack(fill="x", pady=(2, 0))
        self.minimax_mode = tk.StringVar(value="none")
        tk.Label(mm_row, text="MiniMax模板：", font=("Microsoft YaHei", 9)).pack(side="left")
        for val, lbl in (("none", "不用"), ("six_section", "六段式"), ("director", "六段式+导演台"),
                         ("dyt", "dyt导演台")):
            tk.Radiobutton(mm_row, text=lbl, variable=self.minimax_mode, value=val,
                           font=("Microsoft YaHei", 9)).pack(side="left")
        self.minimax_st = tk.Label(mm_row, text="六段式/导演台：逐镜头改写为 主体定义/摘要/保留分析/详细描述/整体声景/非叙事配乐，全片共享主体定义，跨镜无硬切衔接，增强连贯与一致性",
                                   fg="#888", font=("Microsoft YaHei", 8))
        self.minimax_st.pack(side="left", padx=8)
        dlg_row = tk.Frame(sec2); dlg_row.pack(fill="x", pady=(2, 0))
        self.dialogue_major = tk.BooleanVar(value=False)
        tk.Checkbutton(dlg_row, text="对白占比≥60%（剧情更连贯通顺）", variable=self.dialogue_major,
                       font=("Microsoft YaHei", 9)).pack(side="left")
        self.ris_max = tk.BooleanVar(value=False)
        tk.Checkbutton(dlg_row, text="参考图保真max（服饰/身份更一致）", variable=self.ris_max,
                       font=("Microsoft YaHei", 9)).pack(side="left", padx=8)
        self.tts_enabled = tk.BooleanVar(value=False)
        tk.Checkbutton(dlg_row, text="TTS角色配音（整剧音色一致）", variable=self.tts_enabled,
                       font=("Microsoft YaHei", 9)).pack(side="left", padx=8)
        self.dlg_st = tk.Label(dlg_row, text="剧本导演/分幕扩写强制对白密度，生成后校验口播占比",
                               fg="#888", font=("Microsoft YaHei", 8))
        self.dlg_st.pack(side="left", padx=8)

        # 超分（dyt.json RTX 2x 放大）：关闭 / 2倍 / 4倍
        up_row = tk.Frame(sec2); up_row.pack(fill="x", pady=(2, 0))
        tk.Label(up_row, text="超分：", font=("Microsoft YaHei", 9)).pack(side="left")
        # 默认关闭：RTX 放大增加显存占用与耗时，需要超分时由用户按显卡显存显式选择
        self.upscale_var = tk.StringVar(value="关闭")
        self.upscale_cb = ttk.Combobox(up_row, textvariable=self.upscale_var, state="readonly",
                                       values=["关闭", "2倍放大", "4倍放大"], width=12,
                                       font=("Microsoft YaHei", 9))
        self.upscale_cb.pack(side="left", padx=(0, 8))
        tk.Label(up_row, text="RTX 2x 放大：2倍=1 个节点，4倍=两个串联二次放大（省显存）；默认关闭",
                 fg="#888", font=("Microsoft YaHei", 8)).pack(side="left")

        # 故事题材 / 美术风格（ToonFlow 技能库，可选）
        tf_row = tk.Frame(sec2); tf_row.pack(fill="x", pady=(2, 0))
        tk.Label(tf_row, text="故事题材：", font=("Microsoft YaHei", 9)).pack(side="left")
        self.genre_var = tk.StringVar(value="(自动)")
        self.genre_cb = ttk.Combobox(tf_row, textvariable=self.genre_var, state="readonly",
                                     values=self._genre_names(), width=16, font=("Microsoft YaHei", 9))
        self.genre_cb.pack(side="left", padx=(0, 10))
        tk.Label(tf_row, text="美术风格：", font=("Microsoft YaHei", 9)).pack(side="left")
        self.style_var = tk.StringVar(value="(自动)")
        self.style_cb = ttk.Combobox(tf_row, textvariable=self.style_var, state="readonly",
                                     values=self._style_names(), width=22, font=("Microsoft YaHei", 9))
        self.style_cb.pack(side="left")

        out_row = tk.Frame(sec2); out_row.pack(fill="x", pady=(4, 0))
        tk.Label(out_row, text="输出目录：", font=("Microsoft YaHei", 9)).pack(side="left")
        self.outdir = tk.Entry(out_row)
        self.outdir.insert(0, r"G:\视频输出")
        self.outdir.pack(side="left", fill="x", expand=True, padx=(0, 6))
        tk.Button(out_row, text="浏览", command=self._pick_dir).pack(side="left")

        row2 = tk.Frame(sec2); row2.pack(fill="x", pady=(2, 0))
        tk.Label(row2, text="角色JSON路径：", font=("Microsoft YaHei", 9)).pack(side="left")
        self.chars = tk.Entry(row2)
        self.chars.pack(side="left", fill="x", expand=True, padx=(0, 6))
        tk.Button(row2, text="浏览…", command=self._pick_chars).pack(side="left")

        # --- 控制按钮 + 激活 ---
        ctrl = tk.Frame(main); ctrl.pack(fill="x", **pad)
        self.btn_start = tk.Button(ctrl, text="开始生成 ▶", command=self._start, width=14,
                                   bg="#2e7d32", fg="white", font=("Microsoft YaHei", 11))
        self.btn_start.pack(side="left")
        self.btn_stop = tk.Button(ctrl, text="停止", command=self._stop, width=8, state="disabled")
        self.btn_stop.pack(side="left", padx=8)
        # 意外中断保留：有未完成任务时可用，一键续跑
        self.btn_resume = tk.Button(ctrl, text="继续任务 ⟳", command=self._resume_pick, width=12,
                                    state="disabled", font=("Microsoft YaHei", 10))
        self.btn_resume.pack(side="left", padx=(0, 8))
        # AI 实时创作助手：对话式拆解需求→生图→图生视频，随时修改每一步
        tk.Button(ctrl, text="AI 助手 🤖", command=self._open_agent, width=11,
                  font=("Microsoft YaHei", 10)).pack(side="left", padx=(0, 8))
        self.trial_lb = tk.Label(ctrl, text="", anchor="e", fg="#c62828", font=("Microsoft YaHei", 9))
        self.trial_lb.pack(side="right")
        tk.Button(ctrl, text="输入激活码", command=self._ask_activate, width=10).pack(side="right", padx=6)

        # --- 分区三：日志 ---
        sec3 = tk.LabelFrame(main, text=" 3 · 生成日志 ", font=("Microsoft YaHei", 9, "bold"),
                             padx=8, pady=4)
        sec3.pack(fill="both", expand=True, **pad)
        self.log = scrolledtext.ScrolledText(sec3, height=14, state="disabled",
                                             font=("Consolas", 9))
        self.log.pack(fill="both", expand=True)

        self.status = tk.Label(main, text="", anchor="w", fg="#1565c0", font=("Microsoft YaHei", 9))
        self.status.pack(fill="x", padx=10)

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._refresh_trial_label()
        self._refresh_engine_label()
        # 启动后扫描未完成任务，若有则点亮「继续任务」按钮
        self.after(1200, self._refresh_resume_button)

    def _refresh_engine_label(self):
        if self.engine_path:
            self.status_bar.config(bg="#e8f5e9")
            self.movie_st.config(text=f"引擎: {os.path.basename(self.engine_path)}", bg="#e8f5e9")
            # 存储状态条背景
            self.comfy_st.config(bg="#e8f5e9")
        else:
            self.movie_st.config(text="⚠ 未找到引擎 exe", fg="#c62828")
            self.btn_start.configure(state="disabled")

    def _refresh_trial_label(self):
        if self.activation and self._act().is_activated():
            expiry = self._act().activation_expiry()
            self.trial_lb.config(text=f"✅ 已激活 · {expiry}", fg="#2e7d32")
            return
        remaining = TRIAL_LIMIT - self.used
        if remaining > 0 and self.engine_path:
            self.trial_lb.config(text=f"免费试用剩余 {remaining}/{TRIAL_LIMIT} 次 · 激活码", fg="#c62828")
        else:
            self.trial_lb.config(text="⚠ 试用次数已用完，请输入激活码", fg="#c62828")
            self.btn_start.configure(state="disabled")

    # ---------------- 开机自检 ----------------
    def _startup_check(self):
        def work():
            ok, msg = comfy_health()
            self.comfy_ok = ok
            self.after(0, lambda: self._apply_check(ok, msg))
        threading.Thread(target=work, daemon=True).start()

    def _apply_check(self, ok, msg):
        if ok:
            self.comfy_st.config(text=msg, fg="#2e7d32")
            if self.engine_path:
                self.btn_start.configure(state="normal")
        else:
            self.comfy_st.config(text=msg, fg="#c62828")
            self.status.config(text="⚠ ComfyUI 未启动，生成前请先启动 ComfyUI（127.0.0.1:8188）")

    def _recheck(self):
        def work():
            ok, msg = comfy_health()
            self.comfy_ok = ok
            self.after(0, lambda: self._apply_check(ok, msg))
        threading.Thread(target=work, daemon=True).start()

    # ---------------- 交互 ----------------
    def _pick_dir(self):
        d = filedialog.askdirectory()
        if d:
            self.outdir.delete(0, "end"); self.outdir.insert(0, d)

    def _genre_names(self):
        """ToonFlow 故事题材可选（中文名 + 英文 key）。"""
        try:
            from factory import toonflow_skills as _tf
            return ["(自动)"] + sorted(k + " · " + c for k, c in _tf.STORY_GENRES.items())
        except Exception:
            return ["(自动)"]

    def _style_names(self):
        """ToonFlow 美术风格可选（中文名 + 英文 key）。"""
        try:
            from factory import toonflow_skills as _tf
            return ["(自动)"] + sorted(k + " · " + c for k, c in _tf.ART_STYLES.items())
        except Exception:
            return ["(自动)"]

    def _selected_key(self, var, mapping):
        """从 "key · 中文名" 下拉值里解析出 key；"(自动)" 返回 None。"""
        v = var.get().strip()
        if not v or v == "(自动)":
            return None
        key = v.split(" · ")[0].strip()
        return key if key in mapping else None

    def _pick_chars(self):
        f = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if f:
            self.chars.delete(0, "end"); self.chars.insert(0, f)

    def _append_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")
        self.update_idletasks()

    def _ask_activate(self):
        if not self.activation:
            messagebox.showerror("错误", "激活组件未加载")
            return
        win = tk.Toplevel(self)
        win.title("激活")
        win.geometry("480x290")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()

        body = tk.Frame(win); body.pack(padx=20, pady=16, fill="both", expand=True)
        tk.Label(body, text="输入激活码解锁无限使用", font=("Microsoft YaHei", 12, "bold"),
                 fg="#1565c0").pack(pady=(0, 8))
        tk.Label(body, text="激活码为 XXXX-XXXX-XXXX-XXXX（有效期以激活码为准：1天/1周/1月/1年，自激活之日起算）",
                 font=("Microsoft YaHei", 9), fg="#555").pack()

        entry = tk.Entry(body, width=30, font=("Consolas", 11), justify="center")
        entry.pack(pady=12)
        entry.focus_set()

        msg = tk.Label(body, text="", fg="#c62828", font=("Microsoft YaHei", 9))
        msg.pack()

        btns = tk.Frame(body); btns.pack(pady=8)
        tk.Button(btns, text="🚀 购买激活码", command=lambda: open_url(PURCHASE_URL),
                  bg="#ff9800", fg="white", width=14).pack(side="left", padx=6)
        tk.Button(btns, text="确认激活", command=lambda: self._do_activate(entry, msg, win),
                  bg="#2e7d32", fg="white", width=12).pack(side="left", padx=6)
        tk.Button(btns, text="取消", command=win.destroy, width=8).pack(side="left", padx=6)

    def _do_activate(self, entry, msg, win):
        code = entry.get().strip()
        if not code:
            msg.config(text="请输入激活码")
            return
        ok, rmsg = self._act().activate(code)
        if ok:
            self.activated = True
            self._refresh_trial_label()
            self.status.config(text="✅ 激活成功 · " + self._act().activation_expiry())
            win.destroy()
            messagebox.showinfo("激活", f"✅ 激活成功！\n有效期：{self._act().activation_expiry()}")
        else:
            msg.config(text=rmsg)

    # ---------------- 剧本 LLM 总开关：本地推理 ----------------
    def _llm_local_sw_toggle(self):
        """"启用本地推理"总开关：关闭后禁用本地模型单选，强制走自定义提供商 API。"""
        on = self.llm_local_sw.get()
        for rb in getattr(self, "_llm_local_rbs", []):
            rb.config(state="normal" if on else "disabled")
        if not on:
            if self.llm.get() != "custom":
                self.llm.set("custom")
            self.use_provider.set(True)
            self.agent_mode.set("cloud")
            self._refresh_provider_st()
            if not os.path.isfile(self.provider_cfg_path):
                messagebox.showwarning(
                    "本地推理已关闭",
                    "已关闭本地推理：剧本仅可使用“自定义模型(API推理接口)”。\n"
                    "请点击“提供商设置…”填写 模型名称 / API地址 / APIKey / 模型标识 并保存，"
                    "剧本推理将走该远程 API。")
        else:
            self._refresh_provider_st()

    # ---------------- 剧本 LLM：自定义模型（API 推理接口） ----------------
    def _llm_custom_changed(self):
        """选择"自定义模型(API推理接口)"：自动勾选"使用自定义提供商"；
        若尚未配置 providers.json，提示去"提供商设置"填写。"""
        if self.llm.get() != "custom":
            return
        self.use_provider.set(True)
        self.agent_mode.set("cloud")
        self._refresh_provider_st()
        if not os.path.isfile(self.provider_cfg_path):
            messagebox.showwarning(
                "自定义模型需配置提供商",
                "已选择“自定义模型(API推理接口)”。\n"
                "请点击“提供商设置…”填写 模型名称 / API地址 / APIKey / 模型标识 并保存，"
                "剧本推理将走该远程 API。")

    # ---------------- 自定义提供商 ----------------
    def _provider_toggle(self):
        # 勾/取消"使用自定义提供商"时同步"智能体运行方式"
        self.agent_mode.set("cloud")
        self._refresh_provider_st()

    def _agent_mode_toggle(self):
        """仅云端（自定义提供商）：勾选"使用自定义提供商"。"""
        if self.agent_mode.get() == "cloud":
            self.use_provider.set(True)
        self._refresh_provider_st()

    def _refresh_provider_st(self):
        if not hasattr(self, "provider_st"):
            return
        if os.path.isfile(self.provider_cfg_path):
            try:
                with open(self.provider_cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                names = ", ".join(p.get("name", "?") for p in (cfg if isinstance(cfg, list) else []))
                self.provider_st.config(text=f"已配置：{names or '空'}", fg="#2e7d32")
            except Exception:
                self.provider_st.config(text="配置文件无效", fg="#c62828")
        else:
            self.provider_st.config(text="未配置（点“提供商设置”添加）", fg="#888")

    # ---------------- 参考图生图后端（本地 / NVIDIA FLUX API） ----------------
    def _imgapi_cfg(self):
        """读取 exe 旁的 image_api.json；不存在/损坏返回 {}。"""
        try:
            if os.path.isfile(self.imgapi_cfg_path):
                with open(self.imgapi_cfg_path, "r", encoding="utf-8") as f:
                    d = json.load(f)
                return d if isinstance(d, dict) else {}
        except Exception:
            pass
        return {}

    def _refresh_imgapi_st(self):
        d = self._imgapi_cfg()
        if d.get("api_key"):
            host = ""
            try:
                host = (d.get("endpoint") or "").replace("https://", "").split("/")[0]
            except Exception:
                pass
            self.imgapi_st.config(text=f"已配置（{host}）", fg="#2e7d32")
        else:
            self.imgapi_st.config(text="未配置 API Key", fg="#c62828")

    def _image_api_flags(self):
        """按开关把生图后端转成 CLI 参数。返回 (flags, ok, msg)。

        选择云端但未配置完整时 ok=False，msg 为引导提示。
        """
        if self.image_backend.get() != "api":
            return ["--image-backend", "local"], True, ""
        d = self._imgapi_cfg()
        if not (d.get("endpoint") or "").strip() or not (d.get("api_key") or "").strip():
            return [], False, "已选择“云端（NVIDIA FLUX API）”，但尚未填写接口地址/API Key。\n请先点“生图API设置…”填写并保存。"
        return ["--image-backend", "api", "--image-api-config", self.imgapi_cfg_path], True, ""

    def _imgapi_settings(self):
        """“生图API设置…”弹窗：填写 NVIDIA FLUX 接口地址 / API Key / 分辨率 / 步数。"""
        win = tk.Toplevel(self)
        win.title("生图API设置 · NVIDIA FLUX")
        win.geometry("620x430")
        win.transient(self)
        win.grab_set()
        win.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - 620) // 2
        y = self.winfo_rooty() + (self.winfo_height() - 430) // 2
        win.geometry(f"+{x}+{y}")

        d = self._imgapi_cfg()
        vars_ = {
            "endpoint": tk.StringVar(value=(d.get("endpoint") or IMGAPI_DEFAULT_ENDPOINT).strip()),
            "api_key": tk.StringVar(value=(d.get("api_key") or "").strip()),
            "width": tk.StringVar(value=str(d.get("width") or 1024)),
            "height": tk.StringVar(value=str(d.get("height") or 1024)),
            "steps": tk.StringVar(value=str(d.get("steps") or 4)),
        }
        body = tk.Frame(win); body.pack(fill="both", expand=True, padx=14, pady=10)
        rows = [("接口地址", "endpoint", "NVIDIA genai 端点，如 …/v1/genai/black-forest-labs/flux.2-klein-4b"),
                ("API Key", "api_key", "nvapi-…（密钥仅保存在本机 image_api.json，不会写进程序）"),
                ("宽度", "width", "1024（NVIDIA FLUX klein 建议正方形 1024）"),
                ("高度", "height", "1024"),
                ("采样步数", "steps", "4（默认；数值越大质量越高、更慢更耗额度）")]
        for i, (label, key, tip) in enumerate(rows):
            tk.Label(body, text=label + "：", font=("Microsoft YaHei", 9)).grid(
                row=i, column=0, sticky="ne", pady=3)
            e = tk.Entry(body, width=46, font=("Consolas", 9))
            e.grid(row=i, column=1, sticky="w", pady=3)
            if key == "api_key":
                e.config(show="*")
            e.insert(0, vars_[key].get())
            vars_[key + "_e"] = e
            tk.Label(body, text=tip, fg="gray", font=("Microsoft YaHei", 8)).grid(
                row=i, column=2, sticky="w", padx=6)
        tk.Label(body,
                 text="此设置用于“生图方式=云端（NVIDIA FLUX API）”时生成角色/场景/物品参考图；\n"
                      "关闭开关（本地）时不使用该配置，参考图仍由本机 ComfyUI 生成。",
                 fg="#555", font=("Microsoft YaHei", 8), justify="left").grid(
            row=len(rows), column=0, columnspan=3, sticky="w", pady=(10, 2))

        btns = tk.Frame(win); btns.pack(fill="x", padx=14, pady=(0, 12))
        st = tk.Label(btns, text="", fg="#c62828", font=("Microsoft YaHei", 8))
        st.pack(side="left")

        def _get():
            cfg = {}
            for k in ("endpoint", "api_key", "width", "height", "steps"):
                val = vars_[k + "_e"].get().strip()
                cfg[k] = val
            for k in ("width", "height", "steps"):
                try:
                    cfg[k] = int(cfg[k])
                except (TypeError, ValueError):
                    cfg[k] = 1024 if k != "steps" else 4
            return cfg

        def _save():
            cfg = _get()
            if not cfg["endpoint"]:
                st.config(text="请填写接口地址"); return
            if not cfg["api_key"]:
                st.config(text="请填写 API Key"); return
            try:
                with open(self.imgapi_cfg_path, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, ensure_ascii=False, indent=2)
            except Exception as e:
                messagebox.showerror("错误", f"保存失败：{e}", parent=win)
                return
            self._refresh_imgapi_st()
            self.image_backend.set("api")
            self._append_log(f"[生图] API 配置已保存：{self.imgapi_cfg_path}\n")
            win.destroy()

        def _clear():
            try:
                os.remove(self.imgapi_cfg_path)
            except Exception:
                pass
            self._refresh_imgapi_st()
            win.destroy()

        tk.Button(btns, text="保存并启用云端生图", command=_save, bg="#2e7d32", fg="white",
                  font=("Microsoft YaHei", 9)).pack(side="left")
        tk.Button(btns, text="清除配置（回到本地）", command=_clear,
                  font=("Microsoft YaHei", 9)).pack(side="left", padx=8)
        tk.Button(btns, text="关闭", command=win.destroy,
                  font=("Microsoft YaHei", 9)).pack(side="right")

    def _provider_settings(self):
        """提供商设置对话框：编辑 exe 同目录 providers.json。
        四项输入框：模型名称 / API 地址 / API Key / 模型标识，用户自行填写。"""
        win = tk.Toplevel(self)
        win.title("自定义提供商设置")
        win.geometry("580x470")
        win.transient(self); win.grab_set()
        win.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - 580) // 2
        y = self.winfo_rooty() + (self.winfo_height() - 470) // 2
        win.geometry(f"+{x}+{y}")
        # 显式置顶并聚焦，避免 transient+grab_set 导致键盘焦点丢失、输入框无法输入
        win.lift()
        win.focus_force()
        win.after(60, lambda: self._prov_first_entry and self._prov_first_entry.focus_set())

        tk.Label(win, text="OpenAI 兼容提供商（仅剧本推理；图片/视频仍走本地 ComfyUI）",
                 font=("Microsoft YaHei", 9, "bold")).pack(anchor="w", padx=12, pady=(10, 4))

        form = tk.Frame(win); form.pack(fill="x", padx=12)
        # 四项输入：模型名称 / API 地址 / API Key / 模型标识
        rows = [
            ("name", "模型名称"),
            ("base_url", "API 地址"),
            ("api_key", "API Key"),
            ("chat_model", "模型标识"),
        ]
        # 读取现有配置
        cfg = []
        if os.path.isfile(self.provider_cfg_path):
            try:
                with open(self.provider_cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            except Exception:
                cfg = []
        cur = cfg[0] if cfg else {}
        self._prov_vars = {}
        self._prov_first_entry = None
        for i, (k, lbl) in enumerate(rows):
            tk.Label(form, text=lbl, font=("Microsoft YaHei", 9)).grid(row=i, column=0, sticky="w", pady=4)
            v = tk.StringVar(value=str(cur.get(k, "")))
            e = tk.Entry(form, textvariable=v, width=58, font=("Microsoft YaHei", 9))
            # 注意：不要在此处使用 validate="key" + win.register 校验——在 transient+grab_set
            # 的 Toplevel 上会导致输入框无法输入。改为保存时校验即可。
            e.grid(row=i, column=1, sticky="w", pady=4, padx=6)
            # 点击任意输入框时强制把键盘焦点还给该框（防止 grab 抢占焦点导致无法输入）
            e.bind("<Button-1>", lambda ev, ee=e: (ee.focus_force(), win.lift()))
            self._prov_vars[k] = v
            if self._prov_first_entry is None:
                self._prov_first_entry = e

        tip = tk.Label(win, text="支持任意 OpenAI 兼容 /v1/chat/completions 的服务（NVIDIA Build、DeepSeek、硅基流动、本地 vLLM 等）。\n"
                                 "模型名称仅作标识；模型标识为请求时的 model 字段，如 deepseek-ai/deepseek-v4-flash-0731。",
                       fg="gray", font=("Microsoft YaHei", 8), justify="left")
        tip.pack(anchor="w", padx=12, pady=(6, 2))

        vis_row = tk.Frame(win); vis_row.pack(anchor="w", padx=12, pady=(4, 0))
        self._prov_vision = tk.BooleanVar(value=bool(cur.get("vision", True)))
        tk.Checkbutton(vis_row, text="图片识别（多模态输入，默认开启）：模型可读取参考图片理解角色/场景",
                       variable=self._prov_vision, font=("Microsoft YaHei", 9)).pack(side="left")

        btns = tk.Frame(win); btns.pack(fill="x", padx=12, pady=(8, 10))
        self._prov_test_btn = tk.Button(btns, text="测试连接", command=lambda: self._test_provider(win),
                                        font=("Microsoft YaHei", 9))
        self._prov_test_btn.pack(side="left", padx=(0, 8))
        self._prov_test_st = tk.Label(btns, text="", fg="#888", font=("Microsoft YaHei", 8))
        self._prov_test_st.pack(side="left")
        def _save():
            data = [{"name": self._prov_vars["name"].get().strip() or "custom",
                     "base_url": self._prov_vars["base_url"].get().strip(),
                     "api_key": self._prov_vars["api_key"].get().strip(),
                     "chat_model": self._prov_vars["chat_model"].get().strip(),
                     "vision": bool(self._prov_vision.get()),
                     "max_tokens": 8192, "timeout": 240, "default": True}]
            if not data[0]["base_url"]:
                messagebox.showwarning("提示", "请填写 API 地址", parent=win); return
            if len(data[0]["base_url"]) > 500:
                messagebox.showwarning("提示", "API 地址过长（≤500 字符）", parent=win); return
            try:
                with open(self.provider_cfg_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                messagebox.showerror("错误", f"保存失败：{e}", parent=win); return
            self.use_provider.set(True)
            self._refresh_provider_st()
            self._append_log(f"[提供商] 配置已保存：{self.provider_cfg_path}\n")
            win.destroy()
        tk.Button(btns, text="保存并启用", command=_save, bg="#2e7d32", fg="white",
                  font=("Microsoft YaHei", 9)).pack(side="left")
        def _clear():
            try:
                os.remove(self.provider_cfg_path)
            except Exception:
                pass
            self.use_provider.set(False)
            self._refresh_provider_st()
            win.destroy()
        tk.Button(btns, text="清除配置", command=_clear, font=("Microsoft YaHei", 9)).pack(side="left", padx=8)
        def _close():
            self._prov_first_entry = None
            win.destroy()
        tk.Button(btns, text="关闭", command=_close, font=("Microsoft YaHei", 9)).pack(side="right")


    def _test_provider(self, win):
        """用当前表单填写的信息发一个最小请求，验证 OpenAI 兼容提供商能否连通。"""
        try:
            from factory.provider import ProviderClient
        except Exception as e:
            messagebox.showerror("测试连接", f"无法加载测试模块：{e}", parent=win)
            return
        base_url = self._prov_vars["base_url"].get().strip()
        api_key = self._prov_vars["api_key"].get().strip()
        chat_model = self._prov_vars["chat_model"].get().strip()
        if not base_url:
            messagebox.showwarning("提示", "请先填写 API 地址", parent=win)
            return
        if not chat_model:
            messagebox.showwarning("提示", "请先填写推理模型", parent=win)
            return
        self._prov_test_btn.config(state="disabled", text="测试中…")
        self._prov_test_st.config(text="正在连接…", fg="#888")
        win.update_idletasks()

        def _run():
            try:
                client = ProviderClient({
                    "name": self._prov_vars["name"].get().strip() or "custom",
                    "base_url": base_url,
                    "api_key": api_key,
                    "chat_model": chat_model,
                    "max_tokens": 512, "timeout": 180,
                })
                ok, msg = client.test_connection()
                return ok, msg
            except Exception as e:
                return False, f"测试异常：{e}"

        # 后台线程测试，避免阻塞 UI；完成后回到主线程刷新界面
        def _worker():
            result = _run()
            win.after(0, lambda: self._show_test_result(win, result))
        threading.Thread(target=_worker, daemon=True).start()

    def _show_test_result(self, win, result):
        """测试完成后回到主线程刷新按钮状态与提示。"""
        ok, msg = result
        if not win.winfo_exists():
            return
        self._prov_test_btn.config(state="normal", text="测试连接")
        if ok:
            self._prov_test_st.config(text="✓ " + msg, fg="#2e7d32")
            self._append_log(f"[提供商] 测试连接成功：{msg}\n")
        else:
            self._prov_test_st.config(text="✗ " + msg, fg="#c62828")
            self._append_log(f"[提供商] 测试连接失败：{msg}\n")

    # ---------------- 生成 ----------------
    def _start(self):
        story = self.story_txt.get("1.0", "end").strip()
        if not story:
            messagebox.showwarning("提示", "请先输入故事梗概")
            return
        if not self.engine_path:
            messagebox.showerror("错误", "未找到引擎 exe")
            return
        if not self.comfy_ok:
            # 允许但提示，先再自检一次
            if not messagebox.askyesno("ComfyUI 可能未启动",
                                       "检测到 ComfyUI 可能未启动（127.0.0.1:8188）。\n\n仍要继续吗？"):
                return
        # 试用检查
        if not self.activated:
            if self.used >= TRIAL_LIMIT:
                messagebox.showwarning(
                    "试用已用完",
                    "免费试用次数已用完（2/2）。\n请购买激活码并激活后继续使用（有效期以激活码为准：1天/1周/1月/1年）。")
                self._ask_activate()
                return
            if not messagebox.askyesno("免费试用",
                f"本次为【免费试用】第 {self.used + 1}/{TRIAL_LIMIT} 次。\n"
                "成功生成成片会计入一次试用。仍要继续吗？"):
                return

        # 生图后端预检：选了云端但未配置时先引导（本地模式不受影响）
        _, _iok, _imsg = self._image_api_flags()
        if not _iok:
            messagebox.showwarning("生图方式", _imsg)
            return
        # 输出目录：默认 G:/视频输出，每次任务在其下新建时间戳子目录（防止旧数据被覆盖）
        _out_base = self.outdir.get().strip() or r"G:\视频输出"
        self.this_outdir = os.path.join(_out_base, time.strftime("%Y%m%d_%H%M%S"))
        os.makedirs(self.this_outdir, exist_ok=True)
        self.this_script_path = os.path.join(self.this_outdir, "script.json")

        args = [self.engine_path, story,
                "--target-seconds", self.dur.get().strip() or "300",
                "--llm", self.llm.get(),
                "--megapixels", self.mp.get().strip() or "0.2",
                "--steps", self.steps.get().strip() or "16",
                "--aspect", ASPECT_MAP.get(self.aspect_var.get(), "9:16 (Portrait Widescreen)"),
                "--output", self.this_outdir,
                "--resume", "--yes"]
        chars = self.chars.get().strip()
        if chars and os.path.isfile(chars):
            args += ["--characters-json", chars]
        # 自定义提供商：剧本推理走远程 OpenAI 兼容 API
        if self.use_provider.get() and os.path.isfile(self.provider_cfg_path):
            args += ["--provider-config", self.provider_cfg_path]
        # MiniMax 六段式模板 + 对白占比
        args += self._minimax_flags()
        # 超分：关闭 / 2倍 / 4倍（RTX 2x：2倍=调用 dyt.json 1 个 RTX 节点，
        # 4倍=调用两个 RTX 2x 节点串联二次放大，避免一次 4x 崩显存）
        up = self.upscale_var.get()
        if up == "2倍放大":
            args += ["--upscale", "2x"]
        elif up == "4倍放大":
            args += ["--upscale", "4x"]
        else:
            args += ["--upscale", "off"]
        # ToonFlow 故事题材 / 美术风格
        try:
            from factory import toonflow_skills as _tf
            g = self._selected_key(self.genre_var, _tf.STORY_GENRES)
            s = self._selected_key(self.style_var, _tf.ART_STYLES)
            if g:
                args += ["--genre", g]
            if s:
                args += ["--art-style", s]
        except Exception:
            pass

        # 阶段 A：先生成剧本（--plan-only），预览确认后再进入画面生成（阶段 B）
        self._stage = "script"
        args.append("--plan-only")

        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.this_trial = not self.activated  # 记录本次是否计为试用
        self._append_log("$ " + " ".join(args) + "\n\n")
        self.proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, encoding="utf-8", errors="replace")
        threading.Thread(target=self._read_output, daemon=True).start()

    def _read_output(self):
        try:
            for line in iter(self.proc.stdout.readline, ""):
                self._append_log(line)
        except Exception as e:
            self._append_log(f"[错误] {e}\n")
        rc = self.proc.wait()
        self.after(0, lambda: self._finish(rc))

    def _finish(self, rc):
        # 阶段 A 结束：剧本已生成 → 弹审查窗；确认后进入阶段 B（生成画面）
        if getattr(self, "_stage", None) == "script" and rc == 0 and os.path.isfile(self.this_script_path):
            self.btn_start.configure(state="normal")
            self.btn_stop.configure(state="disabled")
            self._refresh_trial_label()
            self.after(0, self._show_review_dialog)
            return
        # AI 审核/修改完成 → 重新弹审查窗（剧本已被引擎更新）
        if getattr(self, "_stage", None) == "review" and rc == 0 and os.path.isfile(self.this_script_path):
            self._append_log("\n[AI 审核完成，请再次确认剧本]\n")
            self.btn_start.configure(state="normal")
            self.btn_stop.configure(state="disabled")
            self._refresh_trial_label()
            self.after(0, self._show_review_dialog)
            return
        # 阶段 B1（--images-only）完成：自动打开文件夹预览参考图，60 秒无操作自动继续
        if getattr(self, "_stage", None) == "images" and rc == 0:
            self.btn_start.configure(state="normal")
            self.btn_stop.configure(state="disabled")
            self.after(0, self._on_images_done)
            return
        final = os.path.join(self.this_outdir, "final_drama.mp4")
        success = rc == 0 and os.path.isfile(final)
        if success:
            # 试用扣次由引擎在成功成片时统一处理，此处仅刷新剩余次数显示
            self.used = int(self._act().used_trials())
            self._append_log(f"\n✅ 完成！成片：{final}\n")
            self._maybe_open_movie(final)
        else:
            self._append_log(f"\n进程退出码 {rc}（未成功产出成片，不计入试用）\n")
            self._append_log("[i] 任务已保留：可点击「继续任务」按钮随时续跑未完成的任务\n")
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self._refresh_trial_label()
        self._refresh_resume_button()
        if self.used >= TRIAL_LIMIT and not self.activated:
            # 试用用完：自动弹出激活码对话框 + 购买入口
            messagebox.showwarning(
                "免费试用次数已用完",
                "您已完成 2 部免费试生成。\n\n"
                "请输入激活码解锁无限使用（有效期以激活码为准：1天/1周/1月/1年，到期需重新购买）。\n"
                "如需购买激活码，可点击下方“购买”前往官方店铺。")
            self._ask_activate()

    def _maybe_open_movie(self, final):
        try:
            self.movie_st.config(text=f"已生成 {os.path.basename(final)}", fg="#2e7d32")
        except Exception:
            pass

    # ---------------- 剧本审查（阶段 A → B） ----------------
    def _show_review_dialog(self):
        """剧本生成后弹审查窗：左栏可编辑的分镜 JSON 列表，右栏翻译对照。

        提供 翻译 / 还原 / 保存 / 接受 / AI审核 / 输入修改要求 / 取消。
        """
        try:
            with open(self.this_script_path, "r", encoding="utf-8") as f:
                script = json.load(f)
        except Exception as e:
            messagebox.showerror("错误", f"读取剧本失败：{e}\n{self.this_script_path}")
            return

        win = tk.Toplevel(self)
        win.title("剧本审查 · 分镜 JSON（左）→ 翻译对照（右）")
        win.geometry("1240x700")
        win.transient(self)
        win.grab_set()
        win.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - 1240) // 2
        y = self.winfo_rooty() + (self.winfo_height() - 700) // 2
        win.geometry(f"+{x}+{y}")

        pane = tk.PanedWindow(win, orient="horizontal", sashwidth=5, bg="#ccc")
        pane.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        # ---- 左栏：分镜 JSON（可编辑）----
        left = tk.Frame(pane); pane.add(left, minsize=560, stretch="always")
        tk.Label(left, text="分镜 JSON 列表（可直接编辑，改后点\"保存\"写回）",
                 font=("Microsoft YaHei", 9, "bold"), fg="#333").pack(anchor="w", padx=4, pady=(0, 2))
        left_wrap = tk.Frame(left); left_wrap.pack(fill="both", expand=True)
        json_txt = tk.Text(left_wrap, font=("Consolas", 10), wrap="none",
                           undo=True, autoseparators=True, maxundo=50)
        json_txt.pack(side="left", fill="both", expand=True)
        lsb = tk.Scrollbar(left_wrap, command=json_txt.yview); lsb.pack(side="right", fill="y")
        json_txt.configure(yscrollcommand=lsb.set)
        json_txt.insert("1.0", _script_pretty_json(script))
        self._review_json_txt = json_txt
        self._review_script_path = self.this_script_path

        # ---- 右栏：翻译对照（只读）----
        right = tk.Frame(pane); pane.add(right, minsize=560, stretch="always")
        tk.Label(right, text="翻译对照（英文 → 中文）",
                 font=("Microsoft YaHei", 9, "bold"), fg="#333").pack(anchor="w", padx=4, pady=(0, 2))
        right_wrap = tk.Frame(right); right_wrap.pack(fill="both", expand=True)
        trans_txt = tk.Text(right_wrap, font=("Microsoft YaHei", 9), wrap="word",
                            state="disabled", fg="#1a1a1a", bg="#f7f7f2")
        trans_txt.pack(side="left", fill="both", expand=True)
        tsb = tk.Scrollbar(right_wrap, command=trans_txt.yview); tsb.pack(side="right", fill="y")
        trans_txt.configure(yscrollcommand=tsb.set)
        self._review_trans_txt = trans_txt
        self._review_win = win

        # ---- 底部按钮 ----
        btns = tk.Frame(win)
        btns.pack(fill="x", padx=10, pady=8)
        tk.Button(btns, text="🌐 专业翻译", command=lambda: self._review_translate(),
                  bg="#1565c0", fg="white", font=("Microsoft YaHei", 9)).pack(side="left")
        tk.Button(btns, text="↩ 还原", command=lambda: self._review_restore(),
                  font=("Microsoft YaHei", 9)).pack(side="left", padx=6)
        tk.Button(btns, text="💾 保存修改", command=lambda: self._review_save(),
                  font=("Microsoft YaHei", 9)).pack(side="left")

        def _accept():
            # 仅用户显式确认才推进：先保存左栏编辑内容，再进入画面生成
            if self._review_save():
                win.destroy()
                self._start_phase_b_images()
        tk.Button(btns, text="✅ 确认提交，进入下一步", command=_accept,
                  bg="#2e7d32", fg="white", font=("Microsoft YaHei", 10)).pack(side="left", padx=10)

        def _ai_review():
            # 云端需提供商；本地走引擎内建的本地 LLM 审核
            if self.agent_mode.get() == "cloud" and (not self.use_provider.get()
                                                     or not os.path.isfile(self.provider_cfg_path)):
                messagebox.showwarning("提示", "未配置自定义提供商，无法云端 AI 审核。\n请先在“提供商设置…”中配置。", parent=win)
                return
            self._review_save()
            win.destroy()
            self._run_review("")
        tk.Button(btns, text="🤖 AI 审核修改", command=_ai_review,
                  font=("Microsoft YaHei", 9)).pack(side="left", padx=2)

        def _custom_review():
            if not self.use_provider.get() or not os.path.isfile(self.provider_cfg_path):
                messagebox.showwarning("提示", "未配置自定义提供商，无法 AI 修改。\n请先在“提供商设置…”中配置。", parent=win)
                return
            inst = simpledialog.askstring("输入修改要求",
                                          "告诉 AI 如何修改剧本（如：结局要有反转、多加一个反派、台词更口语化）：",
                                          parent=win)
            if inst is None:
                return
            self._review_save()
            win.destroy()
            self._run_review(inst or "")
        tk.Button(btns, text="✏️ 按要求修改", command=_custom_review,
                  font=("Microsoft YaHei", 9)).pack(side="left")
        tk.Button(btns, text="取消", command=win.destroy,
                  font=("Microsoft YaHei", 9)).pack(side="right")

        # ---- 操作提示：不再自动跳转，编辑后需手动确认提交 ----
        tk.Label(win, text="提示词/分镜可直接在左栏点击编辑（点击正文不会自动跳转）："
                           "改后点「保存修改」→「确认提交」才进入下一步；AI 审核/按要求修改会基于已保存内容。",
                 fg="#1565c0", font=("Microsoft YaHei", 9), wraplength=1180,
                 justify="left").pack(fill="x", padx=10, pady=(0, 6))

    # ---------------- 剧本审查：JSON 编辑 + 翻译 ----------------
    def _review_load_script(self):
        """从右栏 Text 解析出 script dict；失败返回 None 并提示。"""
        try:
            raw = self._review_json_txt.get("1.0", "end")
            data = json.loads(raw)
            if not isinstance(data, dict) or "shots" not in data:
                raise ValueError("缺少 shots 数组")
            return data
        except Exception as e:
            messagebox.showerror("解析失败", f"左栏 JSON 无法解析：{e}\n\n请检查分镜 JSON 格式。",
                                 parent=self._review_win)
            return None

    def _review_save(self):
        """把左栏编辑后的 JSON 写回 script.json。返回是否成功。"""
        data = self._review_load_script()
        if data is None:
            return False
        try:
            with open(self._review_script_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._append_log(f"[剧本审查] 已保存编辑：{self._review_script_path}\n")
            return True
        except Exception as e:
            messagebox.showerror("保存失败", f"{e}", parent=self._review_win)
            return False

    def _review_restore(self):
        """清空右栏翻译对照，恢复未翻译状态。"""
        self._review_trans_txt.configure(state="normal")
        self._review_trans_txt.delete("1.0", "end")
        self._review_trans_txt.insert("1.0", "（已还原 —— 点击\"翻译\"可在右侧生成英文→中文对照）")
        self._review_trans_txt.configure(state="disabled")

    def _review_translate(self):
        """把剧本中英文字段翻译成中文，在右栏逐镜对照显示。

        翻译后端跟随"智能体运行方式"：云端走自定义提供商，本地走本机 LLM。
        """
        cloud = self.agent_mode.get() == "cloud"
        if cloud and (not self.use_provider.get() or not os.path.isfile(self.provider_cfg_path)):
            messagebox.showwarning("提示", "未配置自定义提供商，无法云端翻译。\n请先在“提供商设置…”中配置。",
                                   parent=self._review_win)
            return
        script = self._review_load_script()
        if script is None:
            return
        # 用当前剧本重新翻译前，先展示"翻译中"
        self._review_trans_txt.configure(state="normal")
        self._review_trans_txt.delete("1.0", "end")
        self._review_trans_txt.insert("1.0",
                                      "正在翻译英文分镜…（云端）" if cloud else "正在翻译英文分镜…（本地 LLM）")
        self._review_trans_txt.configure(state="disabled")

        def _worker():
            try:
                blocks = _script_english_blocks(script)
                if cloud:
                    trans = _translate_blocks_via_provider(self.provider_cfg_path, blocks)
                elif self.llm.get() == "custom":
                    # 自定义模型(API推理)必须走云端翻译
                    trans = _translate_blocks_via_provider(self.provider_cfg_path, blocks)
                else:
                    trans = _translate_blocks_via_local(self.provider_cfg_path, blocks, self.llm.get())
                win.after(0, lambda: self._review_show_translation(blocks, trans))
            except Exception as e:
                err = str(e)
                win.after(0, lambda: self._review_translate_error(err))

        threading.Thread(target=_worker, daemon=True).start()

    def _review_show_translation(self, blocks, trans):
        """把逐块翻译结果写入右栏（原文 → 译文对照）。"""
        self._review_trans_txt.configure(state="normal")
        self._review_trans_txt.delete("1.0", "end")
        lines = []
        for blk in blocks:
            key = blk["key"]
            en = blk["text"]
            zh = trans.get(key, "")
            lines.append(f"▶ {blk['label']}")
            lines.append(f"  英：{en}")
            lines.append(f"  中：{zh or '（未翻译）'}")
            lines.append("")
        self._review_trans_txt.insert("1.0", "\n".join(lines))
        self._review_trans_txt.configure(state="disabled")

    def _review_translate_error(self, err):
        self._review_trans_txt.configure(state="normal")
        self._review_trans_txt.delete("1.0", "end")
        self._review_trans_txt.insert("1.0", f"翻译失败：{err}")
        self._review_trans_txt.configure(state="disabled")

    def _minimax_flags(self):
        """把 MiniMax 六段式/导演台模板与对白占比选项转成 CLI 参数列表。"""
        flags = []
        mm = getattr(self, "minimax_mode", None)
        if mm is not None and mm.get() in ("six_section", "director", "dyt"):
            flags += ["--minimax-template", mm.get()]
        dlg = getattr(self, "dialogue_major", None)
        if dlg is not None and dlg.get():
            flags += ["--dialogue-ratio", "0.6"]
        ris = getattr(self, "ris_max", None)
        if ris is not None and ris.get():
            flags += ["--ref-image-size", "max"]
        tts = getattr(self, "tts_enabled", None)
        if tts is not None and tts.get():
            flags += ["--tts"]
        return flags

    def _run_review(self, instruction):
        """用引擎的 --review 重新规划剧本（AI 审核/修改），完成后回到审查窗。"""
        args = [self.engine_path, "--plan-only", "--script-json", self.this_script_path,
                "--output", self.this_outdir, "--review"]
        if instruction and instruction.strip():
            args += ["--review-instruction", instruction.strip()]
        if self.use_provider.get() and os.path.isfile(self.provider_cfg_path):
            args += ["--provider-config", self.provider_cfg_path]
        args += self._minimax_flags()
        self._stage = "review"
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self._append_log("$ " + " ".join(args) + "\n\n")
        self.proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, encoding="utf-8", errors="replace")
        threading.Thread(target=self._read_output, daemon=True).start()

    def _start_phase_b_images(self):
        """阶段 B1：只生成角色/场景/物品参考图（--images-only）。"""
        args = [self.engine_path, "--script-json", self.this_script_path,
                "--output", self.this_outdir,
                "--images-only"]
        chars = self.chars.get().strip()
        if chars and os.path.isfile(chars):
            args += ["--characters-json", chars]
        if self.use_provider.get() and os.path.isfile(self.provider_cfg_path):
            args += ["--provider-config", self.provider_cfg_path]
        iflags, iok, imsg = self._image_api_flags()
        if not iok:
            messagebox.showwarning("生图方式", imsg)
            return
        args += iflags
        self._stage = "images"
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self._append_log("$ " + " ".join(args) + "\n\n")
        self.proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, encoding="utf-8", errors="replace")
        threading.Thread(target=self._read_output, daemon=True).start()

    def _start_phase_b_videos(self):
        """阶段 B2：复用已有参考图生成全部镜头视频并拼接成片（--skip-images）。"""
        args = [self.engine_path, "--script-json", self.this_script_path,
                "--output", self.this_outdir,
                "--steps", self.steps.get().strip() or "16",
                "--megapixels", self.mp.get().strip() or "0.2",
                "--aspect", ASPECT_MAP.get(self.aspect_var.get(), "9:16 (Portrait Widescreen)"),
                "--resume",
                "--skip-images"]
        chars = self.chars.get().strip()
        if chars and os.path.isfile(chars):
            args += ["--characters-json", chars]
        if self.use_provider.get() and os.path.isfile(self.provider_cfg_path):
            args += ["--provider-config", self.provider_cfg_path]
        args += self._minimax_flags()
        # 超分：关闭 / 2倍 / 4倍（RTX 2x：2倍=调用 dyt.json 1 个 RTX 节点，
        # 4倍=调用两个 RTX 2x 节点串联二次放大，避免一次 4x 崩显存）
        up = self.upscale_var.get()
        if up == "2倍放大":
            args += ["--upscale", "2x"]
        elif up == "4倍放大":
            args += ["--upscale", "4x"]
        else:
            args += ["--upscale", "off"]
        self._stage = "render"
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self._append_log("$ " + " ".join(args) + "\n\n")
        self.proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, encoding="utf-8", errors="replace")
        threading.Thread(target=self._read_output, daemon=True).start()

    def _on_images_done(self):
        """参考图生成完成：自动打开文件夹预览，60 秒无操作自动继续生成视频。"""
        try:
            subprocess.Popen(["explorer", self.this_outdir])
        except Exception:
            try:
                os.startfile(self.this_outdir)
            except Exception:
                pass
        win = tk.Toplevel(self)
        win.title("参考图已生成")
        win.geometry("540x260")
        win.transient(self)
        win.grab_set()
        win.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - 540) // 2
        y = self.winfo_rooty() + (self.winfo_height() - 260) // 2
        win.geometry(f"+{x}+{y}")

        body = tk.Frame(win); body.pack(fill="both", expand=True, padx=16, pady=14)
        tk.Label(body, text="✅ 角色/场景/物品参考图已生成", font=("Microsoft YaHei", 12, "bold"),
                 fg="#2e7d32").pack(anchor="w")
        tk.Label(body, text="已自动打开图片所在文件夹，可自行修改/替换图片后继续，或直接跳过：",
                 font=("Microsoft YaHei", 9), fg="#555").pack(anchor="w", pady=(6, 0))
        tk.Label(body, text=self.this_outdir, font=("Consolas", 8), fg="#1565c0",
                 justify="left").pack(anchor="w")
        count_lb = tk.Label(body, text="", font=("Microsoft YaHei", 10, "bold"), fg="#c62828")
        count_lb.pack(anchor="w", pady=(8, 0))

        btns = tk.Frame(body); btns.pack(fill="x", pady=(10, 0))
        tk.Button(btns, text="▶ 立即继续生成视频", command=lambda: _go(),
                  bg="#2e7d32", fg="white", font=("Microsoft YaHei", 10)).pack(side="left")
        tk.Button(btns, text="取消", command=win.destroy,
                  font=("Microsoft YaHei", 9)).pack(side="right")

        self._img_auto_id = None
        self._img_left = 60

        def _go():
            if self._img_auto_id is not None:
                try:
                    win.after_cancel(self._img_auto_id)
                except Exception:
                    pass
                self._img_auto_id = None
            win.destroy()
            self._start_phase_b_videos()

        def _tick():
            self._img_left -= 1
            if self._img_left <= 0:
                count_lb.config(text="60 秒内无操作，自动继续生成视频…")
                _go()
                return
            count_lb.config(text=f"⏱ {self._img_left} 秒内无操作将自动继续生成视频…")
            self._img_auto_id = win.after(1000, _tick)

        def _cancel(_evt=None):
            if self._img_auto_id is not None:
                try:
                    win.after_cancel(self._img_auto_id)
                except Exception:
                    pass
                self._img_auto_id = None
            count_lb.config(text="（已取消自动继续，请点击按钮操作）", fg="#888")

        win.bind("<Button-1>", _cancel, add="+")
        win.bind("<Key>", _cancel, add="+")
        self._img_auto_id = win.after(1000, _tick)

    # ---------------- 意外中断保留：继续任务 ----------------
    def _find_resumable_tasks(self):
        """扫描输出根目录下未完成的任务（被中断/未正常结束），供「继续任务」使用。"""
        import glob as _glob
        base = self.outdir.get().strip() or r"G:\视频输出"
        tasks = []
        try:
            entries = sorted(os.listdir(base), reverse=True)
        except Exception:
            return tasks
        for name in entries:
            d = os.path.join(base, name)
            if not os.path.isdir(d):
                continue
            st = task_state.load(d)
            if st is None:
                # 旧版任务无状态文件：有剧本但没有任何成片 → 视为未完成
                if not os.path.isfile(os.path.join(d, "script.json")):
                    continue
                if _glob.glob(os.path.join(d, "final_drama*.mp4")):
                    continue
                has_refs = os.path.isfile(os.path.join(d, "refs_result.json"))
                st = {"title": "", "phase": "shots" if has_refs else "refs",
                      "done_shots": 0, "total_shots": 0, "params": {}}
            else:
                if st.get("done"):
                    continue
                if task_state.pid_alive(st.get("pid")):
                    continue  # 任务正在运行中，不列入可继续列表
            tasks.append((d, st))
        return tasks

    def _refresh_resume_button(self):
        try:
            tasks = self._find_resumable_tasks()
        except Exception:
            tasks = []
        try:
            self.btn_resume.configure(state="normal" if tasks else "disabled")
        except Exception:
            pass

    def _resume_pick(self):
        if getattr(self, "proc", None) and self.proc.poll() is None:
            messagebox.showwarning("继续任务", "当前有任务正在运行，请等它完成或先停止。")
            return
        tasks = self._find_resumable_tasks()
        if not tasks:
            messagebox.showinfo("继续任务", "没有发现未完成的任务。\n\n"
                                "生成被中断（关机/崩溃/停止）后任务会保留在输出目录，\n可随时点此继续。")
            return
        if len(tasks) == 1:
            self._continue_task(*tasks[0])
            return
        win = tk.Toplevel(self)
        win.title("选择要继续的任务")
        win.geometry("780x320")
        win.transient(self)
        win.grab_set()
        win.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - 780) // 2
        y = self.winfo_rooty() + (self.winfo_height() - 320) // 2
        win.geometry(f"+{x}+{y}")
        tk.Label(win, text="以下任务未正常完成，选择一个继续：",
                 font=("Microsoft YaHei", 10)).pack(anchor="w", padx=12, pady=(12, 4))
        lb = tk.Listbox(win, font=("Consolas", 9))
        lb.pack(fill="both", expand=True, padx=12, pady=4)
        for d, st in tasks:
            lb.insert("end", task_state.brief(st) + "   |   " + d)
        lb.selection_set(0)

        def _go(_ev=None):
            sel = lb.curselection()
            if sel:
                win.destroy()
                self._continue_task(*tasks[sel[0]])
        lb.bind("<Double-Button-1>", _go)
        btns = tk.Frame(win)
        btns.pack(fill="x", padx=12, pady=(0, 12))
        tk.Button(btns, text="继续所选任务 ▶", command=_go, width=16,
                  bg="#2e7d32", fg="white").pack(side="left")
        tk.Button(btns, text="取消", command=win.destroy, width=10).pack(side="left", padx=8)

    def _continue_task(self, task_dir, st):
        """接管任务目录为本 GUI 当前任务，按已保存的进度自动选择续跑阶段。"""
        self.this_outdir = task_dir
        self.this_script_path = os.path.join(task_dir, "script.json")
        params = st.get("params") or {}
        has_script = os.path.isfile(self.this_script_path)
        has_refs = os.path.isfile(os.path.join(task_dir, "refs_result.json"))
        if not has_script:
            # 剧本阶段就中断了：用保存的剧情梗概重跑阶段 A（生成剧本 → 审查窗）
            if not params.get("story"):
                messagebox.showerror("继续任务", "该任务未保存剧情梗概，无法自动继续，请重新开始生成。")
                return
            self._relaunch_task(params, mode="plan")
            return
        if not has_refs:
            self._relaunch_task(params, mode="images")
            return
        self._relaunch_task(params, mode="videos")

    def _state_flags(self, params):
        """从任务状态参数快照还原引擎参数；快照缺省项回退到当前界面设置。"""
        args = []

        def put(flag, key, fallback=None):
            v = params.get(key)
            if v is None or v == "":
                v = fallback
            if v is None or v == "":
                return
            args.append(flag)
            args.append(str(v))

        put("--target-seconds", "target_seconds", self.dur.get().strip() or "300")
        put("--llm", "llm", self.llm.get())
        put("--megapixels", "megapixels", self.mp.get().strip() or "0.2")
        put("--steps", "steps", self.steps.get().strip() or "16")
        put("--aspect", "aspect", ASPECT_MAP.get(self.aspect_var.get(),
                                                  "9:16 (Portrait Widescreen)"))
        if params.get("characters_json") and os.path.isfile(params["characters_json"]):
            args += ["--characters-json", params["characters_json"]]
        if params.get("provider_config") and os.path.isfile(params["provider_config"]):
            args += ["--provider-config", params["provider_config"]]
        if params.get("minimax_template"):
            args += ["--minimax-template", params["minimax_template"]]
        try:
            _dr = float(params.get("dialogue_ratio") or 0)
        except Exception:
            _dr = 0
        if _dr > 0:
            args += ["--dialogue-ratio", str(_dr)]
        if params.get("upscale") in ("off", "2x", "4x"):
            args += ["--upscale", params["upscale"]]
        if params.get("image_backend") == "api":
            iflags, iok, _imsg = self._image_api_flags()
            if iok:
                args += iflags
        if params.get("ref_image_size"):
            args += ["--ref-image-size", params["ref_image_size"]]
        if params.get("genre"):
            args += ["--genre", params["genre"]]
        if params.get("art_style"):
            args += ["--art-style", params["art_style"]]
        if params.get("tts_enabled"):
            args += ["--tts"]
        return args

    def _relaunch_task(self, params, mode):
        """mode: plan=重跑剧本阶段 / images=补参考图 / videos=续跑镜头视频并成片"""
        if mode == "plan":
            args = [self.engine_path, params.get("story") or "",
                    "--output", self.this_outdir, "--plan-only"] + self._state_flags(params)
            self._stage = "script"
        elif mode == "images":
            args = [self.engine_path, "--script-json", self.this_script_path,
                    "--output", self.this_outdir, "--images-only"] + self._state_flags(params)
            self._stage = "images"
        else:
            args = [self.engine_path, "--script-json", self.this_script_path,
                    "--output", self.this_outdir, "--resume", "--skip-images", "--yes"] \
                + self._state_flags(params)
            self._stage = "render"
        self._append_log("$ " + " ".join(args) + "\n\n")
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, encoding="utf-8", errors="replace")
        threading.Thread(target=self._read_output, daemon=True).start()

    # ---------------- AI 实时创作助手 ----------------
    def _open_agent(self):
        win = getattr(self, "_agent_win", None)
        if win is not None and win.winfo_exists():
            win.lift()
            return
        win = tk.Toplevel(self)
        self._agent_win = win
        win.title("AI 实时创作助手")
        win.geometry("600x660")
        head = tk.Frame(win)
        head.pack(fill="x", padx=10, pady=(10, 4))
        tk.Label(head, text="用一句话描述需求，AI 自动拆解步骤并逐一生成（文生图→图生视频）；"
                            "生成中可随时发消息修改后续步骤。",
                 font=("Microsoft YaHei", 9), fg="#555", wraplength=470,
                 justify="left").pack(side="left", anchor="w")
        tk.Button(head, text="打开任务文件夹", width=12,
                  command=self._agent_open_dir).pack(side="right")
        self._agent_text = scrolledtext.ScrolledText(win, state="disabled",
                                                     font=("Microsoft YaHei", 9),
                                                     wrap="word")
        self._agent_text.pack(fill="both", expand=True, padx=10, pady=4)
        for tag, fg in {"user": "#1565c0", "agent": "#212121", "system": "#6a1b9a",
                        "error": "#c62828", "action": "#2e7d32"}.items():
            self._agent_text.tag_configure(tag, foreground=fg)
        row = tk.Frame(win)
        row.pack(fill="x", padx=10, pady=(0, 10))
        self._agent_entry = tk.Entry(row, font=("Microsoft YaHei", 10))
        self._agent_entry.pack(side="left", fill="x", expand=True)
        self._agent_entry.bind("<Return>", lambda _e: self._agent_send())
        tk.Button(row, text="发送", command=self._agent_send, width=8,
                  bg="#1565c0", fg="white").pack(side="left", padx=(6, 0))
        tk.Button(row, text="停止", command=self._agent_stop,
                  width=6).pack(side="left", padx=(4, 0))
        self._agent_append("system", "示例：帮我生成一张古风武侠图，然后做成15秒打斗短视频")

    def _agent_append(self, tag, msg):
        t = getattr(self, "_agent_text", None)
        if t is None:
            return
        try:
            t.configure(state="normal")
            t.insert("end", str(msg) + "\n", tag)
            t.see("end")
            t.configure(state="disabled")
        except Exception:
            pass

    def _agent_emit(self, **ev):
        """Agent 工作线程 → GUI（after 回主线程刷新）。"""
        typ = ev.get("type")

        def apply():
            t = ev.get("text") or ""
            if typ == "plan":
                self._agent_append("agent", t or f"计划：{ev.get('title')}")
                for i, s in enumerate(ev.get("steps") or []):
                    mark = "✅" if i < (ev.get("done") or 0) else "□"
                    self._agent_append("system", f"  {mark} 步骤{i + 1} [{s.get('type')}] {s.get('name')}")
            elif typ == "step_start":
                self._agent_append("system", f"▶ 步骤{ev.get('index') + 1} {ev.get('name')}（{ev.get('typ')}）开始…")
            elif typ == "step_done":
                self._agent_append("action", f"✅ 步骤{ev.get('index') + 1} {ev.get('name')} 完成（{ev.get('secs')}s）\n   {ev.get('path')}")
            elif typ == "step_fail":
                self._agent_append("error", f"❌ 步骤{ev.get('index') + 1} {ev.get('name')} 失败：{t}")
            elif typ == "done":
                self._agent_append("agent" if ev.get("ok") else "error", ("🎉 " if ev.get("ok") else "") + t)
                if ev.get("ok"):
                    for o in ev.get("outputs") or []:
                        self._agent_append("action", f"   产出：{o.get('path')}")
            elif typ == "reply":
                self._agent_append("agent", t)
            elif typ == "log":
                self._agent_append("system", t)
            elif typ == "error":
                self._agent_append("error", t)
        try:
            self._agent_win.after(0, apply)
        except Exception:
            pass

    def _make_agent(self):
        from factory import agent as _agent_mod
        prov = None
        try:
            from factory import provider as _prov
            cfg = None
            if self.use_provider.get() and os.path.isfile(self.provider_cfg_path):
                cfg = _prov.pick_provider(path=self.provider_cfg_path)
            if cfg is None:
                cfg = _prov.pick_provider()  # 自动发现 providers.json
            if cfg:
                prov = _prov.ProviderClient(cfg, log=lambda s: None)
        except Exception:
            prov = None
        backend, cfgp = "local", None
        iflags, iok, _imsg = self._image_api_flags()
        if iok and "--image-backend" in iflags:
            backend = "api"
            if "--image-api-config" in iflags:
                cfgp = iflags[iflags.index("--image-api-config") + 1]
        return _agent_mod.Agent(emit=self._agent_emit, provider=prov,
                                image_backend=backend, image_api_config=cfgp,
                                log=lambda s: self._agent_append("system", str(s)))

    def _agent_send(self):
        txt = self._agent_entry.get().strip()
        if not txt:
            return
        self._agent_entry.delete(0, "end")
        self._agent_append("user", txt)
        ag = getattr(self, "_agent", None)
        if ag is not None and ag.busy:
            ag.send(txt)
            self._agent_append("system", "（已发送，将在当前步骤结束后处理）")
            return
        ag = self._make_agent()
        self._agent = ag
        threading.Thread(target=ag.run, args=(txt,), daemon=True).start()

    def _agent_stop(self):
        ag = getattr(self, "_agent", None)
        if ag is not None and ag.busy:
            ag.stop()
            self._agent_append("system", "已请求停止当前任务…")

    def _agent_open_dir(self):
        ag = getattr(self, "_agent", None)
        d = ag.out_dir if ag is not None else ""
        if d and os.path.isdir(d):
            try:
                subprocess.Popen(["explorer", d])
            except Exception:
                os.startfile(d)
        else:
            messagebox.showinfo("AI 助手", "还没有任务目录（先发送一条生成指令）。")

    def _stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self._append_log("\n[已请求停止]\n")
            self.btn_stop.configure(state="disabled")

    def _on_close(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        self.destroy()


class _NullActivation:
    """激活组件未加载时的占位。"""
    def is_activated(self):
        return False
    def used_trials(self):
        return 0
    def consume_trial(self):
        return 1
    def activate(self, code):
        return False, "组件未加载"


if __name__ == "__main__":
    try:
        DramaGUI().mainloop()
    except Exception:
        import traceback
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "drama_gui_crash.log"), "w", encoding="utf-8") as f:
                traceback.print_exc(file=f)
                f.write("cwd: " + os.getcwd() + "\n")
        except Exception:
            pass
        raise
