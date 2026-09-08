# -*- coding: utf-8 -*-
"""短剧工厂 —— ComfyUI API prompt 生成器。

基于两个已验证工作流：
- imageai.json  : Z-Image turbo 文生图（LLM 视觉概念设计师增强 -> Z-Image 8步 -> 定妆图）
- h3hbai.json   : MiniMax H3 ref2va 多参视频（参考图 + 原生音频 -> 竖屏视频）

所有模型名 / 采样参数均取自上述工作流，保证可运行。

视频生成默认切换到外部 dyt.json 工作流（见 factory/workflow_dyt.py）；
仅在 --workflow 指向的文件不存在时回退到内置 h3hbai ref2va 节点图。
"""
import os
import random

# ============================================================
# 模型与采样常量（取自 imageai.json / h3hbai.json）
# ============================================================

# --- LLM（llama.cpp 视觉 / 剧本）---
LLM_MODEL = "Qwen3.5-9B-heretic.Q8_0.gguf"
LLM_MMPROJ = "mmproj-Qwen3.5-9B-Q8_0.gguf"
LLM_CHAT_HANDLER = "Qwen3.5"
LLM_N_CTX = 8192
LLM_VRAM_LIMIT = 512

# LLM 可选配置：
#   qwen3.5 : 9B VLM（快，带视觉，max_tokens 受 n_ctx=8192 限制）
#   qwen3.8 : 27B UD 纯文本（Qwen3.8-27B-UD-Q4_K_S.gguf，qwen35 架构，无 mmproj，
#              n_ctx 16384 支持单次长输出；vram_limit 决定卸载层数：
#              实测 13GB→38 层 2.4t/s，21GB→61 层 7.3t/s（62 层最优点，全量 65 层反而 6.7t/s））
LLM_CONFIGS = {
    "qwen3.5": dict(model=LLM_MODEL, mmproj=LLM_MMPROJ,
                    chat_handler=LLM_CHAT_HANDLER, n_ctx=LLM_N_CTX,
                    vram_limit=LLM_VRAM_LIMIT),
    "qwen3.8": dict(model="Qwen3.8-27B-UD-Q4_K_S.gguf", mmproj="None",
                    chat_handler="None", n_ctx=16384, vram_limit=21),
    "qwen3.8ag": dict(model="Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive-IQ2_M.gguf",
                      mmproj="None", chat_handler="None", n_ctx=8192, vram_limit=14),
}
LLM_DEFAULT = "qwen3.8"

LLM_PARAMS = dict(
    max_tokens=1024, top_k=30, top_p=0.9, min_p=0.05, typical_p=1,
    temperature=0.8, repeat_penalty=1, frequency_penalty=0, presence_penalty=1,
    mirostat_mode=0, mirostat_eta=0.1, mirostat_tau=5, state_uid=0,
    reasoning_budget=0,  # 关闭 Qwen3.8 <think> 思考块，保证 JSON 直接输出
)

# --- Z-Image（文生图）---
Z_CLIP = "qwen_3_4b.safetensors"
Z_CLIP_TYPE = "lumina2"
Z_VAE = "ae.safetensors"
Z_UNET = "z_image_turbo_bf16.safetensors"
Z_STEPS = 8
Z_CFG = 1.0
Z_SAMPLER = "res_multistep"
Z_SCHEDULER = "simple"
Z_DENOISE = 1.0
Z_SHIFT = 3.0
Z_WIDTH = 1024
Z_HEIGHT = 1024

# --- MiniMax H3（ref2va 视频）---
H3_CLIP = "qwen3vl_32b_h3_ultra_uncensored_heretic_int8_convrot.safetensors"
H3_CLIP_TYPE = "minimax"
H3_VIDEO_VAE = "minimax_h3_video_vae_fp16.safetensors"
H3_AUDIO_VAE = "minimax_h3_audio_vae_fp32.safetensors"
H3_UNET = "minimax_h3_ref2va_pruned_int8_convrot.safetensors"
H3_TESPEED = dict(processing_control_value=1, processing_percent_1=0.1,
                  processing_percent_2=0.9, mcs=2, device="gpu")
H3_ASPECT = "9:16 (Portrait Widescreen)"
H3_MEGAPIXELS = 0.4
H3_MULTIPLE = 32
H3_SCHEDULER = "simple"
H3_STEPS = 16
H3_DENOISE = 1.0
H3_SAMPLER = "euler"
H3_REF_IMAGE_SIZE = "match"
H3_FPS = 24
H3_BIT_DEPTH = 8

# --- 输出前缀 ---
CHAR_PREFIX = "drama_factory/character"
SHOT_PREFIX = "drama_factory/shots"


def frames_for_duration(duration_sec):
    """秒 -> 帧数（24fps，snap 到 H3 的 17k+5 网格，124 ≈ 5s）。"""
    frames = max(5, round(duration_sec * H3_FPS))
    length = frames + (5 - (frames % 17)) % 17
    return int(length)


# ============================================================
# LLM 剧本生成
# ============================================================
def _llm_loader_inputs(llm_config):
    """从 LLM 配置生成 loader+parameters 两个节点。"""
    cfg = dict(LLM_CONFIGS[llm_config or LLM_DEFAULT])
    loader = {
        "1": {"class_type": "llama_cpp_model_loader", "inputs": {
            "model": cfg.pop("model"), "mmproj": cfg.pop("mmproj"),
            "chat_handler": cfg.pop("chat_handler"), "n_ctx": cfg.pop("n_ctx"),
            "vram_limit": cfg.pop("vram_limit"),
            "image_min_tokens": 0, "image_max_tokens": 0}},
    }
    return loader, cfg


def build_script_prompt(story, system_prompt, max_tokens=4096, temperature=0.7, llm=None):
    """返回 LLM 剧本导演 API prompt。LLM 文本经 ShowText 输出到 history。

    max_tokens/temperature 可覆盖默认值（长剧本需加大 max_tokens，配合 n_ctx）。
    """
    seed = random.randint(0, 2 ** 63)
    llm_params = dict(LLM_PARAMS)
    llm_params["max_tokens"] = max_tokens   # 多镜头 JSON 较长
    llm_params["temperature"] = temperature  # 保证 JSON 稳定
    loader, _ = _llm_loader_inputs(llm)
    return {
        **loader,
        "2": {"class_type": "llama_cpp_parameters", "inputs": llm_params},
        "3": {"class_type": "llama_cpp_instruct_adv", "inputs": {
            "llama_model": ["1", 0], "parameters": ["2", 0],
            "preset_prompt": "Empty - Nothing",
            "custom_prompt": story,
            "system_prompt": system_prompt,
            "inference_mode": "one by one",
            "max_frames": 24, "max_size": 896,
            "seed": seed, "force_offload": False, "save_states": False}},
        "4": {"class_type": "ShowText|pysssss", "inputs": {"text": ["3", 0]}},
    }


def build_image_enhance_prompt(text, llm=None):
    """返回 LLM 视觉概念设计师 API prompt（imageai 流程），输出增强后的绘图提示词。"""
    seed = random.randint(0, 2 ** 63)
    from .prompts import image_enhancer_prompt
    loader, _ = _llm_loader_inputs(llm)
    return {
        **loader,
        "2": {"class_type": "llama_cpp_parameters", "inputs": dict(LLM_PARAMS)},
        "3": {"class_type": "llama_cpp_instruct_adv", "inputs": {
            "llama_model": ["1", 0], "parameters": ["2", 0],
            "preset_prompt": "Normal - Describe",
            "custom_prompt": text,
            "system_prompt": image_enhancer_prompt(),
            "inference_mode": "images", "max_frames": 24, "max_size": 896,
            "seed": seed, "force_offload": False, "save_states": False}},
        "4": {"class_type": "ShowText|pysssss", "inputs": {"text": ["3", 0]}},
    }


# ============================================================
# 长剧本分幕扩写（max_tokens 4096 上限，长剧拆多幕逐幕生成）
# ============================================================
def _llm_api(system_prompt, user_prompt, max_tokens=None, llm=None):
    """构造分幕扩写 LLM API prompt。

    qwen3.8 支持单次长输出（12000），qwen3.5 保持 4096。
    temperature 压低提高 JSON 服从性（Qwen3.8 思考外溢时仍能干净收尾）。
    """
    seed = random.randint(0, 2 ** 63)
    llm_params = dict(LLM_PARAMS)
    if max_tokens is None:
        # qwen3.8 系（27B）支持单次长输出 12000；其余靠 4096
        key = llm or LLM_DEFAULT
        # 按配置的 n_ctx 判断：≥16384 视为长上下文模型，可单次长输出
        max_tokens = 12000 if (key in LLM_CONFIGS and LLM_CONFIGS[key].get("n_ctx", 0) >= 16384) else 4096
    llm_params["max_tokens"] = max_tokens
    llm_params["temperature"] = 0.2
    loader, _ = _llm_loader_inputs(llm)
    return {
        **loader,
        "2": {"class_type": "llama_cpp_parameters", "inputs": llm_params},
        "3": {"class_type": "llama_cpp_instruct_adv", "inputs": {
            "llama_model": ["1", 0], "parameters": ["2", 0],
            "preset_prompt": "Empty - Nothing",
            "custom_prompt": user_prompt,
            "system_prompt": system_prompt,
            "inference_mode": "one by one",
            "max_frames": 24, "max_size": 896,
            "seed": seed, "force_offload": False, "save_states": False}},
        "4": {"class_type": "ShowText|pysssss", "inputs": {"text": ["3", 0]}},
    }


def build_outline_prompt(story, target_seconds, n_shots, n_beats, characters, llm=None,
                         preset_title=None, minimax_mode=None, dialogue_ratio=None,
                         genre_text='', art_text=''):
    """分幕扩写第 1 步：总纲（title/style/scenes/props/beats）。

    characters: 预置角色 dict 列表，LLM 不生成，只使用。
    minimax_mode/dialogue_ratio: 透传给 outline_system_prompt 以加入六段式/对白占比约束。
    """
    from .prompts import outline_system_prompt
    sysp = outline_system_prompt(target_seconds, n_shots, n_beats, characters, preset_title,
                                 minimax_mode=minimax_mode, dialogue_ratio=dialogue_ratio,
                                 genre_text=genre_text, art_text=art_text)
    return _llm_api(sysp, story, llm=llm)


def build_segment_prompt(title, character, style, beat, start, end, count, llm=None,
                         characters=None, scenes=None, props=None, prev_end=None,
                         minimax_mode=None, dialogue_ratio=None, is_first=False,
                         genre_text='', art_text=''):
    """分幕扩写第 2 步：展开某一幕的镜头列表（含角色/场景/物品引用）。
    prev_end: 可选，上一幕末尾画面描述，用于跨幕/跨段无缝衔接。
    minimax_mode/dialogue_ratio/is_first: 透传给 segment_system_prompt 加入六段式/对白占比约束。"""
    from .prompts import segment_system_prompt
    sysp = segment_system_prompt(title, character, style, beat, start, end, count,
                                 characters, scenes, props, prev_end,
                                 minimax_mode=minimax_mode, dialogue_ratio=dialogue_ratio,
                                 is_first=is_first, genre_text=genre_text, art_text=art_text)
    return _llm_api(sysp, f"请扩写第 {start} 到 {end} 幕镜头（共 {count} 个），并衔接上一段结尾。", llm=llm)


# ============================================================
# Z-Image 文生图（定妆图 / 场景参考图）
# ============================================================
def build_zimage_prompt(text, filename_prefix, seed=None, width=Z_WIDTH, height=Z_HEIGHT):
    """返回 Z-Image 文生图 API prompt，SaveImage 保存到 <filename_prefix>。"""
    if seed is None:
        seed = random.randint(0, 2 ** 63)
    return {
        "1": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": Z_CLIP, "type": Z_CLIP_TYPE, "device": "default"}},
        "2": {"class_type": "UNETLoader", "inputs": {
            "unet_name": Z_UNET, "weight_dtype": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": Z_VAE}},
        "4": {"class_type": "ModelSamplingAuraFlow", "inputs": {
            "model": ["2", 0], "shift": Z_SHIFT}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {
            "text": text, "clip": ["1", 0]}},
        "6": {"class_type": "ConditioningZeroOut", "inputs": {
            "conditioning": ["5", 0]}},
        "7": {"class_type": "EmptySD3LatentImage", "inputs": {
            "width": width, "height": height, "batch_size": 1}},
        "8": {"class_type": "KSampler", "inputs": {
            "model": ["4", 0], "positive": ["5", 0], "negative": ["6", 0],
            "latent_image": ["7", 0],
            "seed": seed, "steps": Z_STEPS, "cfg": Z_CFG,
            "sampler_name": Z_SAMPLER, "scheduler": Z_SCHEDULER, "denoise": Z_DENOISE}},
        "9": {"class_type": "VAEDecode", "inputs": {
            "samples": ["8", 0], "vae": ["3", 0]}},
        "10": {"class_type": "SaveImage", "inputs": {
            "images": ["9", 0], "filename_prefix": filename_prefix}},
    }


# ============================================================
# MiniMax H3 ref2va 视频（单镜头）
# ============================================================
def build_shot_video_prompt(shot, ref_images, params=None):
    """返回单镜头 H3 ref2va API prompt，支持多张参考图（角色 + 场景 + 物品）。

    shot       : dict，含 video_prompt / image_prompt / dialogue / duration。
                 shot["refs"] 可选 dict：{"character": "<Picture N>", "scene": ..., "prop": ...}
                         由调用方预先把每张参考图绑定到对应 <Picture N> 标签。
    ref_images : list[str]，ComfyUI input 目录中的参考图文件名，顺序 = <Picture 1..N>。
    params     : 可覆盖采样参数（width/height/length/seed/steps/scheduler 等）；
                 还支持 minimax_mode（"six_section"/"director" 时走六段式模板）与
                 dialogue_ratio（对白目标占比 0~1）与 total/is_first（导演台上下文）。
    """
    p = params or {}
    width = p.get("width")
    height = p.get("height")
    length = p.get("length") or frames_for_duration(shot.get("duration_sec", 5.0))
    seed = p.get("seed") or random.randint(0, 2 ** 63)
    steps = p.get("steps", H3_STEPS)
    scheduler = p.get("scheduler", H3_SCHEDULER)

    # ---- dyt.json 工作流模式（外部 ComfyUI 工作流，默认启用）----
    # 上层把 --workflow 路径放入 params["workflow"]；文件存在则走 dyt 全功能工作流
    wf_path = p.get("workflow") or ""
    if wf_path and os.path.isfile(wf_path):
        from . import workflow_dyt
        return workflow_dyt.build_shot_video_api(shot, ref_images or [], p,
                                                 workflow_path=wf_path)

    ref_images = ref_images or []
    if not ref_images:
        raise ValueError("build_shot_video_prompt 至少需要 1 张参考图")

    # prompt：视频提示词 + 分镜衔接 + Dialogue + <Picture N> 引用标签
    video_prompt = shot.get("video_prompt", "").strip()
    transition = shot.get("transition_prev", "").strip()

    # ---- MiniMax 六段式 / 导演台模板 ----
    # 参数：minimax_mode ∈ {None, "six_section", "director"}，dialogue_ratio ∈ [0,1]
    minimax_mode = p.get("minimax_mode")
    dialogue_ratio = float(p.get("dialogue_ratio", 0.0) or 0.0)
    # 组件 refs（调用方已把角色/场景/物品绑定到 <Picture N>）
    refs = shot.get("refs") or {}

    if minimax_mode:
        # 六段式：把本镜头重组为 主体定义/摘要/保留分析/详细描述/整体声景/非叙事配乐
        from . import minimax_prompt
        mp = dict(p)
        mp["shot_idx"] = int(shot.get("shot", 0) or 0) or 1
        mp["total"] = int(p.get("total", 1) or 1)
        mp["is_first"] = bool(mp.get("is_first"))
        mp["dialogue_ratio"] = dialogue_ratio
        prompt = minimax_prompt.build_six_section_prompt(shot, shot.get("_script", {}), refs, mp)
        # 六段式文本已内嵌 <Picture N> 标签；若完全没有标签，则回退全量引用在句首
        if "<Picture" not in prompt:
            pic_tags = " ".join(f"<Picture {i + 1}>" for i in range(len(ref_images)))
            prompt = f"{pic_tags}:\n{prompt}"
        return _build_shot_video_nodes(shot, ref_images, p, prompt, width, height, length, seed,
                                       steps, scheduler)

    body = video_prompt
    if transition:
        body = f"{body}. Continuity from previous shot: {transition}"
    # dialogue 兼容字符串（旧）与结构化数组（新，每项 speaker+text）
    from . import minimax_prompt as _mp
    dlg_text = _mp.dialogue_to_prompt_text(shot)
    if dlg_text:
        body = f"{body}. Dialogue: {dlg_text}"
        # 说话人锁定（dialogue_rule）：有显式说话人时强制每句台词由冒号前角色本人说出，
        # 禁止把 A 的台词分配给 B——防止视频模型把对白安到错误人物身上
        if _mp.dialogue_has_speaker(shot):
            body += (" [Dialogue rule] Each line must be spoken by exactly the character named before the colon; "
                     "never assign one character's line to another character.")
    # 按 shot["refs"] 提供的标签把对应参考图名词嵌入 prompt（语义指导模型用哪几张图）
    # 默认：如果没给 refs，就把所有图按 <Picture N> 全量引用在句首
    if refs:
        tag_str = " ".join(f"{v}: {body}" for v in refs.values())
        prompt = f"{tag_str}"
    else:
        pic_tags = " ".join(f"<Picture {i + 1}>" for i in range(len(ref_images)))
        prompt = f"{pic_tags}: {body}"

    return _build_shot_video_nodes(shot, ref_images, p, prompt, width, height, length, seed,
                                   steps, scheduler)


def _build_shot_video_nodes(shot, ref_images, params, prompt, width, height, length, seed,
                            steps, scheduler):
    """根据组装好的 prompt 构建 MiniMax H3 ref2va API 节点图。

    供 build_shot_video_prompt 的六段式与普通模式共用，避免重复。
    """
    p = params or {}
    if width is None or height is None:
        res = {
            "10": {"class_type": "ResolutionSelector", "inputs": {
                "aspect_ratio": p.get("aspect_ratio", H3_ASPECT),
                "megapixels": p.get("megapixels", H3_MEGAPIXELS),
                "multiple": p.get("multiple", H3_MULTIPLE)}},
        }
        ref_width = ["10", 0]
        ref_height = ["10", 1]
    else:
        res = {}
        ref_width = width
        ref_height = height

    nodes = {
        **res,
        "1": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": H3_CLIP, "type": H3_CLIP_TYPE, "device": "default"}},
        "2": {"class_type": "VAELoader", "inputs": {"vae_name": H3_VIDEO_VAE}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": H3_AUDIO_VAE}},
        "4": {"class_type": "UNETLoader", "inputs": {
            "unet_name": H3_UNET, "weight_dtype": "default"}},
        # 原 KJ 节点 PathchSageAttentionKJ 已移除：依赖 KJNodes 自定义包，且其
        # SageAttention 对模型有白名单限制，在未安装 KJNodes 的机器上会报错。
        # 改为 UNET 输出直连 TE 加速（原生节点），兼容所有 ComfyUI 环境。
        "6": {"class_type": "TESpeedMiniMaxH3", "inputs": {
            "model": ["4", 0], **H3_TESPEED}},
    }
    # 为每张参考图创建 LoadImage 节点
    load_ids = {}
    for i, img in enumerate(ref_images):
        nid = f"load_{i}"
        nodes[nid] = {"class_type": "LoadImage", "inputs": {"image": img}}
        load_ids[i] = nid
    # H3 参考图注入 ref_images.ref_image_0..N
    ref_in = {f"ref_images.ref_image_{i}": [load_ids[i], 0] for i in range(len(ref_images))}
    # 计算节点序号起点（load 节点占用了 load_0..N key，避开整数冲突）
    nodes["8"] = {"class_type": "MiniMaxH3ReferenceToVideo", "inputs": {
        "clip": ["1", 0], "vae": ["2", 0], "audio_vae": ["3", 0],
        **ref_in,
        "prompt": prompt,
        "width": ref_width, "height": ref_height,
        "length": length, "ref_image_size": H3_REF_IMAGE_SIZE}}
    nodes["9"] = {"class_type": "BasicGuider", "inputs": {
        "model": ["6", 0], "conditioning": ["8", 0]}}
    nodes["10b"] = {"class_type": "BasicScheduler", "inputs": {
        "model": ["6", 0], "scheduler": scheduler, "steps": steps, "denoise": H3_DENOISE}}
    nodes["11"] = {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}}
    nodes["12"] = {"class_type": "KSamplerSelect", "inputs": {"sampler_name": H3_SAMPLER}}
    nodes["13"] = {"class_type": "SamplerCustomAdvanced", "inputs": {
        "noise": ["11", 0], "guider": ["9", 0], "sampler": ["12", 0],
        "sigmas": ["10b", 0], "latent_image": ["8", 1]}}
    nodes["14"] = {"class_type": "VAEDecode", "inputs": {
        "samples": ["13", 0], "vae": ["2", 0]}}
    nodes["15"] = {"class_type": "VAEDecodeAudio", "inputs": {
        "samples": ["13", 0], "vae": ["3", 0]}}
    nodes["16"] = {"class_type": "CreateVideo", "inputs": {
        "images": ["14", 0], "audio": ["15", 0],
        "fps": H3_FPS, "bit_depth": H3_BIT_DEPTH}}
    nodes["17"] = {"class_type": "SaveVideo", "inputs": {
        "video": ["16", 0],
        "filename_prefix": SHOT_PREFIX,
        "format": "auto", "codec": "auto"}}
    return nodes
