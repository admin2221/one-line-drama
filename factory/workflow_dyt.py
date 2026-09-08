# -*- coding: utf-8 -*-
"""dyt.json 视频工作流加载与逐镜头注入。

需求：把短剧工厂的视频生成工作流从内置的 h3hbai(ref2va) 节点图切换为
ComfyUI 里的 dyt.json（MiniMax H3 fl2va 全功能工作流：TE 加速 + 音频 VAE +
RTX 超分 + 显存清理等），提示词改为该工作流的「中文导演式 + 图N参考 + （X-Y秒）
时段」格式。

实现：
1. 读取 dyt.json（ComfyUI 前端导出的 workflow 格式：nodes/links）
2. 把 workflow 格式转换为 API prompt 格式（ComfyUI 可提交的 {"<id>": {...}}）
   - 跳过 mute(2)/bypass(4) 节点与纯 UI 节点（MarkdownNote）
   - widget 值按 schema 顺序映射到 inputs（在线取 /object_info 缓存，离线用内置表）
3. 移除「多轨循环」链（easy multiTrackEditor/TaskOutput/InfoOutput、ImageResizeKJv2、
   Int、ShowText、PreviewImage）——逐镜头 API 提交直接注入值，不需要前端多轨循环
4. 注入单镜头值：prompt / 参考图 / 时长帧数 / 分辨率 / 种子 / 输出前缀

dyt.json 路径可用 --workflow 覆盖；路径不存在时上层回退到旧的 ref2va 节点图。
"""
import json
import os
import urllib.request
import urllib.parse
import urllib.error
import random
import sys

# 默认 dyt.json 路径（用户机器上的 ComfyUI 工作流）
# dyt.json 工作流路径解析（软件目录优先，见下）
if getattr(sys, "frozen", False):
    _APP_DIR = os.path.dirname(sys.executable)  # PyInstaller exe 所在目录
else:
    _APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 工程根目录
_LEGACY_WORKFLOW = r"D:\Comfyui\Comfyui\user\default\workflows\dyt.json"
_WORKFLOW_CANDIDATES = [
    os.path.join(_APP_DIR, "dyt.json"),
    _LEGACY_WORKFLOW,
]


def default_workflow_path():
    """返回第一个存在的 dyt.json 路径；都不存在时返回软件目录候选（报错友好）。"""
    for _p in _WORKFLOW_CANDIDATES:
        if os.path.isfile(_p):
            return _p
    return _WORKFLOW_CANDIDATES[0]


# 兼容旧引用：导入时解析一次（软件目录 dyt.json 优先）
DEFAULT_WORKFLOW_PATH = default_workflow_path()

# 首部废帧数：每个镜头多生成 17 帧废帧（H3 帧数网格为 17k+5，+17 正好一个网格
# 步长，不破坏网格合法性），生成后由 concat.trim_first_frames 裁掉前 17 帧再保存，
# 规避 H3 首段（约 0.7 秒）画面闪烁/黑帧/角色崩坏。
WARMUP_FRAMES = 17

# MiniMax H3 Latent Upscaler 权重（latent_upscale_models 目录）
DEFAULT_LATENT_UPSCALE_MODEL = "minimax_h3_latent_upscaler_3d_fp16.safetensors"

# 纯 UI / 调试节点：不进入 API
_SKIP_TYPES = {"MarkdownNote", "easy multiTrackInfoOutput"}

# 多轨循环链：逐镜头注入时不保留
_MULTITRACK_TYPES = {"easy multiTrackEditor", "easy multiTrackTaskOutput",
                     "easy multiTrackInfoOutput", "ImageResizeKJv2", "Int",
                     "ShowText|pysssss", "PreviewImage"}

WIDGET_TYPES = {"INT", "FLOAT", "STRING", "BOOLEAN", "COMBO", "SEED", "STYLE", "FILENAMES",
                "NUMBER", "XINT", "XSTRING", "XFLOAT", "BATCH", "BOX", "IMAGEUPLOAD",
                "AUDIOUPLOAD", "COMFY_DYNAMICCOMBO_V3", "COMFY_COMBO", "COMFY_STRING",
                "COMFY_INT", "COMFY_FLOAT", "COMFY_BOOLEAN"}

# 离线兜底的 widget 顺序表（来自 ComfyUI /object_info，dyt.json 涉及的节点类型）。
# 在线时优先用 /object_info 实时获取并缓存，离线时用此表，保证两种环境下都能转换。
_STATIC_WIDGET_ORDER = {
    "CLIPLoader": ["clip_name", "type", "device"],
    "UNETLoader": ["unet_name", "weight_dtype"],
    "VAELoader": ["vae_name"],
    "BasicScheduler": ["scheduler", "steps", "denoise"],
    "KSamplerSelect": ["sampler_name"],
    "RandomNoise": ["noise_seed"],
    "TESpeedMiniMaxH3": ["processing_control_value", "processing_percent_1",
                         "processing_percent_2", "mcs", "device"],
    "VRAMCleanup": ["offload_model", "offload_cache"],
    "RAMCleanup": ["clean_file_cache", "clean_processes", "clean_dlls", "retry_times"],
    "CreateVideo": ["fps", "bit_depth"],
    "SaveVideo": ["filename_prefix", "format", "codec"],
    "RTXVideoSuperResolution": ["resize_type", "quality"],
    "MiniMaxH3ReferenceToVideo": ["prompt", "width", "height", "length", "ref_image_size"],
    "LoadImage": ["image"],
    "Int": ["Number"],
    "ResolutionSelector": ["aspect_ratio", "megapixels", "multiple"],
    "easy multiTrackEditor": ["resolution", "format"],
    "easy multiTrackTaskOutput": ["task_index", "prompt_format"],
    "ImageResizeKJv2": ["width", "height", "upscale_method", "keep_proportion",
                        "pad_color", "crop_position", "divisible_by", "device"],
    "PathchSageAttentionKJ": ["sage_attention", "allow_compile"],
    "BasicGuider": [],
    "SamplerCustomAdvanced": [],
    "VAEDecode": [],
    "VAEDecodeAudio": [],
}

# COMFY_DYNAMICCOMBO_V3 选中项对应的子 widget 名
_DYNAMIC_SUBS = {
    ("SaveVideo", "codec"): ["codec.encoding"],
    ("RTXVideoSuperResolution", "resize_type"): ["resize_type.scale"],
}

_object_info_cache = {}


def _is_widget(spec):
    if not isinstance(spec, list) or not spec:
        return False
    t = spec[0]
    if isinstance(t, list):
        return True  # combo
    return isinstance(t, str) and t in WIDGET_TYPES


def _fetch_object_info(comfy_url="http://127.0.0.1:8188", node_type=None, timeout=6):
    """从运行中的 ComfyUI 拉取某节点类型的 object_info；失败返回 {}。"""
    if node_type is not None and node_type in _object_info_cache:
        return _object_info_cache[node_type]
    if node_type is None:
        return {}
    try:
        url = f"{comfy_url}/object_info/{urllib.parse.quote(node_type)}"
        req = urllib.request.Request(url, headers={"User-Agent": "drama-factory"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        info = data.get(node_type, {}) or {}
        _object_info_cache[node_type] = info
        return info
    except Exception:
        return {}


def _widget_names(info, node_type):
    """节点类型的 widget 输入名（schema 声明顺序）。有 object_info 用实时，否则用内置表。"""
    inp = (info.get("input") or {}) if info else {}
    names = []
    for sec in ("required", "optional"):
        for name, spec in (inp.get(sec, {}) or {}).items():
            if _is_widget(spec):
                names.append(name)
    if names:
        return names
    return list(_STATIC_WIDGET_ORDER.get(node_type, []))


def _dynamic_subnames(node_type, wn):
    return _DYNAMIC_SUBS.get((node_type, wn), [])


def load_workflow(path=None):
    """读取 dyt.json workflow 原文 dict。path 缺省用默认路径。"""
    p = path or DEFAULT_WORKFLOW_PATH
    if not os.path.isfile(p):
        raise FileNotFoundError(f"工作流文件不存在：{p}")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def workflow_to_api(wf, comfy_url="http://127.0.0.1:8188"):
    """workflow(前端) 格式 -> API prompt 格式。

    跳过 muted(2)/bypassed(4) 节点与 UI 节点；widget 值按 schema 顺序填充，
    已连线的输入保留 [node_id, slot] 链接。
    """
    nodes = {n["id"]: n for n in wf.get("nodes", [])}
    link_map = {}
    for l in wf.get("links", []):
        link_map[l[0]] = (l[1], l[2], l[3], l[4])

    prompt = {}
    for n in wf.get("nodes", []):
        if n.get("mode", 0) in (2, 4):
            continue  # mute / bypass
        ntype = n.get("type", "")
        if ntype in _SKIP_TYPES:
            continue
        nid = str(n["id"])
        info = _fetch_object_info(comfy_url, ntype)
        inputs = {}
        linked = set()
        for inp in n.get("inputs", []):
            if inp.get("link") is not None and inp["link"] in link_map:
                src_id, src_slot, _, _ = link_map[inp["link"]]
                inputs[inp["name"]] = [str(src_id), src_slot]
                linked.add(inp["name"])
        wnames = _widget_names(info, ntype)
        wv = n.get("widgets_values", []) or []
        wi = 0
        for wn in wnames:
            if wn in inputs or wn in linked:
                # 已连线 widget：跳过对应 widget 值
                if wn == "noise_seed" and wi + 1 < len(wv) and wv[wi + 1] in ("randomize", "fixed"):
                    wi += 2
                else:
                    wi += 1
                continue
            if wn == "noise_seed" and wi + 1 < len(wv) and wv[wi + 1] in ("randomize", "fixed"):
                inputs[wn] = wv[wi]
                wi += 2
                continue
            sub = _dynamic_subnames(ntype, wn)
            if sub:
                # COMFY_DYNAMICCOMBO_V3：先取选中项，再取子 widget
                if wi < len(wv):
                    inputs[wn] = wv[wi]
                wi += 1
                for s in sub:
                    if wi < len(wv):
                        inputs[s] = wv[wi]
                    wi += 1
                continue
            if wi < len(wv):
                inputs[wn] = wv[wi]
                wi += 1
        prompt[nid] = {"class_type": ntype, "inputs": inputs}
    return prompt


def _find_node_by_type(api, class_type):
    for k, v in api.items():
        if v.get("class_type") == class_type:
            return k
    return None


def _find_nodes_by_type(api, class_type):
    return [k for k, v in api.items() if v.get("class_type") == class_type]


def _drop_dangling(api, removed):
    """移除所有直接或间接引用已删除节点 id 的残留节点（如 RTX 链上的
    cleanGpuUsed / UnloadAllModels）。新 dyt.json 中两个 RTX 超分串联，
    中间夹着显存清理节点，移除 RTX 后必须一并清掉，否则 API 提交悬空引用。"""
    removed = set(removed)
    changed = True
    while changed:
        changed = False
        for k, v in list(api.items()):
            if k in removed:
                continue
            refs = [x[0] for x in v.get("inputs", {}).values()
                    if isinstance(x, list) and x and isinstance(x[0], str)]
            if any(r in removed for r in refs):
                api.pop(k, None)
                removed.add(k)
                changed = True
    return removed


def _last_rtx_before(api, create_key, rtx_keys):
    """沿 CreateVideo.images 输入链逆推，返回最接近 CreateVideo 的 RTX 节点 id；
    CreateVideo 已直连 VAEDecode（无 RTX）时返回 None。"""
    if not create_key:
        return None
    cur = api[create_key]["inputs"].get("images")
    nid = cur[0] if isinstance(cur, list) and cur else None
    seen = set()
    while nid and nid not in seen:
        seen.add(nid)
        if nid in rtx_keys:
            return nid
        nxt = None
        for x in api[nid]["inputs"].values():
            if isinstance(x, list) and x and isinstance(x[0], str):
                nxt = x[0]
                break
        nid = nxt
    return None


def build_shot_video_api(shot, ref_images, params=None, workflow_path=None,
                         comfy_url="http://127.0.0.1:8188"):
    """加载 dyt.json -> API prompt -> 注入单镜头值，返回可直接提交的 API dict。

    shot       : dict，含 duration_sec/duration；prompt 文本由调用方组装好放入
                 params["prompt"]（dyt 中文导演式）或本函数按 minimax_mode 组装。
    ref_images : list[str]，ComfyUI input 目录中的参考图文件名（顺序 = 图1..N）。
    params     : 支持 width/height（强制分辨率）、megapixels/aspect_ratio（走
                 ResolutionSelector）、steps/scheduler、seed、length、save_prefix、
                 no_rtx（去掉 RTX 超分）、minimax_mode、dialogue_ratio、total/is_first。
    """
    wf = load_workflow(workflow_path)
    api = workflow_to_api(wf, comfy_url=comfy_url)
    p = params or {}

    # ---- 移除多轨循环链节点 ----
    for k in [k for k, v in api.items() if v.get("class_type") in _MULTITRACK_TYPES]:
        api.pop(k, None)

    # ---- 定位关键节点 ----
    h3_key = _find_node_by_type(api, "MiniMaxH3ReferenceToVideo")
    seed_key = _find_node_by_type(api, "RandomNoise")
    save_key = _find_node_by_type(api, "SaveVideo")
    rtx_keys = _find_nodes_by_type(api, "RTXVideoSuperResolution")
    if not h3_key:
        raise RuntimeError("dyt.json 中未找到 MiniMaxH3ReferenceToVideo 节点")

    h3 = api[h3_key]["inputs"]

    # ---- 采样参数：params 提供 steps/scheduler/denoise 时注入 BasicScheduler，
    #      否则保留 dyt.json 工作流内的设定（跟随工作流 UI，如新工作流默认 simple/2 步）----
    sched_key = _find_node_by_type(api, "BasicScheduler")
    if sched_key:
        _si = api[sched_key]["inputs"]
        for _k, _v in (("steps", p.get("steps")), ("scheduler", p.get("scheduler")),
                       ("denoise", p.get("denoise"))):
            if _v is not None:
                _si[_k] = _v

    # ---- 参考图：为每张图建 LoadImage 节点并注入 ref_images.ref_image_0..N ----
    ref_images = ref_images or []
    load_ids = {}
    for i, img in enumerate(ref_images):
        lid = f"dyt_load_{i}"
        api[lid] = {"class_type": "LoadImage", "inputs": {"image": img}}
        load_ids[i] = lid
    for i in range(len(ref_images)):
        h3[f"ref_images.ref_image_{i}"] = [load_ids[i], 0]
    # ref_image_size：默认 'match'（官方文档：'max' 保留 2048px 短边，身份保真更强，
    # 适合角色/服饰颜色一致性要求高的镜头；代价是参考 token 随每一步采样，速度更慢）
    h3["ref_image_size"] = p.get("ref_image_size", "match")
    # 移除未用的 ref_videos/ref_audios 输入
    for k in list(h3.keys()):
        if k in ("ref_videos.ref_video_0", "ref_video_audios.ref_video_audio_0",
                 "ref_audios.ref_audio_0") and not isinstance(h3[k], list):
            h3.pop(k, None)

    # ---- 分辨率：优先强制 width/height，否则 ResolutionSelector ----
    if p.get("width") and p.get("height"):
        h3["width"] = int(p["width"])
        h3["height"] = int(p["height"])
    else:
        res_key = f"dyt_res"
        api[res_key] = {"class_type": "ResolutionSelector", "inputs": {
            "aspect_ratio": p.get("aspect_ratio", "9:16 (Portrait Widescreen)"),
            "megapixels": float(p.get("megapixels", 0.4)),
            "multiple": int(p.get("multiple", 32))}}
        h3["width"] = [res_key, 0]
        h3["height"] = [res_key, 1]

    # ---- 时长帧数（H3 的 17k+5 网格，与 ref2va 一致）----
    from .generator import frames_for_duration
    length = p.get("length") or frames_for_duration(
        float(str(shot.get("duration_sec") or shot.get("duration") or 5).strip() or 5))
    # 首部废帧：多生成 17 帧（一个网格步长），调用方在保存前裁掉
    length = int(length) + WARMUP_FRAMES
    p["warmup_frames"] = WARMUP_FRAMES  # 回写给调用方（params 按引用传入）
    h3["length"] = length

    # ---- prompt ----
    prompt = p.get("prompt")
    if not prompt:
        from . import minimax_prompt
        refs = shot.get("refs") or {}
        mm = p.get("minimax_mode")
        if mm in ("six_section", "director"):
            mp = dict(p)
            mp["shot_idx"] = int(shot.get("shot", 0) or 0) or 1
            mp["total"] = int(p.get("total", 1) or 1)
            mp["is_first"] = bool(p.get("is_first"))
            prompt = minimax_prompt.build_six_section_prompt(shot, shot.get("_script", {}), refs, mp)
        else:
            prompt = minimax_prompt.build_dyt_shot_prompt(
                shot, shot.get("_script", {}), refs, ref_images,
                tts_mode=bool(p.get("tts_mode")))
    h3["prompt"] = prompt

    # ---- 种子 ----
    seed = p.get("seed")
    if seed is None:
        seed = random.randint(0, 2 ** 63)
    if seed_key:
        api[seed_key]["inputs"]["noise_seed"] = seed

    # ---- 输出前缀 ----
    if save_key:
        prefix = p.get("save_prefix") or "drama_factory/shots"
        api[save_key]["inputs"]["filename_prefix"] = prefix

    # ---- RTX 超分：可选关闭 ----
    # ---- RTX 超分：--upscale 控制（off=关闭 / 2x=保留 1 个 / 4x=保留全部串联）。
    #      --no-rtx-upscale 兼容（等价 off）。dyt.json 中两个 RTX 2x 串联实现 4 倍，
    #      中间夹 cleanGpu/UnloadAll 显存清理，二次放大避免一次 4x 崩显存。----
    up = p.get("upscale")
    if up is None and p.get("no_rtx"):
        up = "off"
    if up is not None and rtx_keys:
        create_key = _find_node_by_type(api, "CreateVideo")
        dec_key = _find_node_by_type(api, "VAEDecode")
        up_s = str(up).lower()
        if up_s in ("off", "0", "false"):
            # 关闭：移除全部 RTX，CreateVideo 直连 VAEDecode
            if create_key and dec_key:
                api[create_key]["inputs"]["images"] = [dec_key, 0]
            for k in rtx_keys:
                api.pop(k, None)
            _drop_dangling(api, rtx_keys)
        elif up_s in ("2x", "1", "2", "2.0"):
            # 2 倍：只保留紧邻 CreateVideo 的最后一个 RTX，其余移除
            keep = _last_rtx_before(api, create_key, rtx_keys)
            if keep and dec_key:
                api[keep]["inputs"]["images"] = [dec_key, 0]
                if create_key:
                    api[create_key]["inputs"]["images"] = [keep, 0]
                _others = [k for k in rtx_keys if k != keep]
                for k in _others:
                    api.pop(k, None)
                _drop_dangling(api, _others)
        # 其它（4x/2 等）：保留全部 RTX 串联（dyt.json 默认两个 2x = 4 倍）

    # ---- MiniMax H3 Latent Upscaler：低清 latent 神经网络放大（修复脸部崩坏）----
    # 原理：H3 在低分辨率（如 0.2~0.4MP）采样时脸部细节不足，RTX 像素放大不会
    # 产生新细节，放大后脸部崩坏/糊。改为在 latent 空间用专用 3D 神经网络放大：
    #   sampler.output → LTXVSeparateAVLatent(拆 video/audio) → 3D Upscaler(视频) →
    #   LTXVConcatAVLatent(拼回 AV) → VAEDecode / VAEDecodeAudio → CreateVideo
    # 启用后自动绕过 RTX 像素放大（latent 放大已含空间超分，二次像素放大无益）。
    latent_up = p.get("latent_upscale") or 0.0
    try:
        latent_up = float(latent_up)
    except (TypeError, ValueError):
        latent_up = 0.0
    if latent_up > 0:
        sampler_key = _find_node_by_type(api, "SamplerCustomAdvanced")
        if not sampler_key:
            raise RuntimeError("启用 latent upscale 时未找到 SamplerCustomAdvanced 节点")
        vaes = _find_nodes_by_type(api, "VAELoader")
        if len(vaes) < 2:
            raise RuntimeError("启用 latent upscale 时需要 2 个 VAELoader（video + audio vae）")
        create_key = _find_node_by_type(api, "CreateVideo")
        if not create_key:
            raise RuntimeError("启用 latent upscale 时未找到 CreateVideo 节点")

        sep, up, cat = "dyt_lu_sep", "dyt_lu_up", "dyt_lu_cat"
        vdec, adec = "dyt_lu_vdec", "dyt_lu_adec"
        api[sep] = {"class_type": "LTXVSeparateAVLatent",
                    "inputs": {"av_latent": [sampler_key, 0]}}
        # 前置显存清理：H3 采样完成后先卸载其权重并清空模型缓存，再加载 upscaler。
        # 否则 16GB 显存同时驻留 H3 12B 权重 + upscaler + 放大后 latent 会 OOM（尤其 4 倍放大）。
        pre_clean = "dyt_lu_preclean"
        api[pre_clean] = {"class_type": "VRAMCleanup",
                          "inputs": {"anything": [sep, 0],
                                     "offload_model": True,
                                     "offload_cache": True}}
        api[up] = {"class_type": "MinimaxH3LatentUpscaler3D", "inputs": {
            "latent": [pre_clean, 0],
            "model_name": p.get("latent_upscale_model") or DEFAULT_LATENT_UPSCALE_MODEL,
            # new API DynamicCombo：主输入 = 选中 option 的 key，子输入 = "<input>.<sub>" 扁平 key
            "mode": "scale by multiplier",
            "mode.scale": max(1.0, min(4.0, latent_up)),
            "align": int(p.get("latent_upscale_align", 32)),
            "enable_temporal_chunking": True,
            "force_unload": True,
            "device": "cuda",
            "precision": p.get("latent_upscale_precision") or "fp16",
        }}
        api[cat] = {"class_type": "LTXVConcatAVLatent", "inputs": {
            "video_latent": [up, 0],
            "audio_latent": [sep, 1]}}
        # 保留 VRAMCleanup 透传（清显存语义），否则放大后的 latent 直连解码
        vram_keys = _find_nodes_by_type(api, "VRAMCleanup")
        if vram_keys:
            # 原 anything 输入接 sampler.output，改接放大后的 AV latent
            vram = api[vram_keys[0]]["inputs"]
            for k in list(vram.keys()):
                if isinstance(vram[k], list) and vram[k][0] == sampler_key:
                    vram[k] = [cat, 0]
                    break
            samples_src = [vram_keys[0], 0]
        else:
            samples_src = [cat, 0]
        api[vdec] = {"class_type": "VAEDecode",
                     "inputs": {"samples": samples_src, "vae": [vaes[0], 0]}}
        api[adec] = {"class_type": "VAEDecodeAudio",
                     "inputs": {"samples": samples_src, "vae": [vaes[1], 0]}}
        api[create_key]["inputs"]["images"] = [vdec, 0]
        api[create_key]["inputs"]["audio"] = [adec, 0]
        # 移除旧解码/RTX 节点（注入后不再被引用，残留会重复解码/放大），
        # 并清理 RTX 链上残留的显存清理节点（新工作流两个 RTX 串联）
        _old = [k for k, v in api.items() if v.get("class_type") in
                ("VAEDecode", "VAEDecodeAudio", "RTXVideoSuperResolution")]
        _old = [k for k in _old if k != vdec and k != adec]
        for k in _old:
            api.pop(k, None)
        _drop_dangling(api, _old)

    return api


def validate_api(api, comfy_url="http://127.0.0.1:8188"):
    """把 API prompt 提交到 ComfyUI /prompt 做结构校验（不真正入队执行）。

    返回 (ok, msg)：ok=False 时 msg 为校验错误文本。ComfyUI 的 /prompt 只做
    验证与入队，校验失败会返回 400 带错误明细，可用来在开发期验证转换正确性。
    """
    try:
        import urllib.request as _u
        data = json.dumps({"prompt": api}).encode("utf-8")
        req = _u.Request(comfy_url + "/prompt", data=data,
                         headers={"Content-Type": "application/json"}, method="POST")
        with _u.urlopen(req, timeout=30) as r:
            r.read()
        return True, "workflow API 校验通过"
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:2000]
        return False, body
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
