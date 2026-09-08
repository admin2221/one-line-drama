# -*- coding: utf-8 -*-
"""生成短剧工厂的 ComfyUI 画布工作流（可视化版）。

架构与 factory/drama_factory.py 一致：
  一句话 -> LLM 剧本导演 -> 角色定妆图(Z-Image) -> 逐镜头 H3 ref2va(共用定妆图) -> 拼接

输出：ComfyUI/user/default/workflows/短剧工厂.json（默认 8 镜头）
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

N_SHOTS = 8
DST = r"D:\Comfyui\Comfyui\user\default\workflows\短剧工厂.json"

NODES = []
LINKS = []
_nid = 100
_lid = 5000


def add_node(node_type, pos, widgets=None, title=None, size=None, collapsed=False,
             color=None, bgcolor=None):
    global _nid
    n = {
        "id": _nid, "type": node_type,
        "pos": list(pos), "size": size or [200, 100],
        "flags": {"collapsed": collapsed} if collapsed else {},
        "order": len(NODES), "mode": 0,
        "inputs": [], "outputs": [],
        "properties": {"Node name for S&R": node_type},
        "widgets_values": widgets if widgets is not None else [],
    }
    if title:
        n["title"] = title
    if color:
        n["color"] = color
    if bgcolor:
        n["bgcolor"] = bgcolor
    nid = _nid
    NODES.append(n)
    _nid += 1
    return nid


def connect(src_id, src_slot, dst_id, dst_slot, typ):
    global _lid
    link_id = _lid
    _lid += 1
    LINKS.append([link_id, src_id, src_slot, dst_id, dst_slot, typ])
    ins = node(dst_id)["inputs"]
    if isinstance(dst_slot, int) and dst_slot < len(ins):
        ins[dst_slot]["link"] = link_id
    elif isinstance(dst_slot, str):
        for inp in ins:
            if inp["name"] == dst_slot:
                inp["link"] = link_id
    outs = node(src_id)["outputs"]
    if isinstance(src_slot, int) and src_slot < len(outs):
        outs[src_slot].setdefault("links", []).append(link_id)
    elif isinstance(src_slot, str):
        for out in outs:
            if out["name"] == src_slot:
                out.setdefault("links", []).append(link_id)


def node(nid):
    return next(n for n in NODES if n["id"] == nid)


def w_in(name, typ, wid=None, link=None, label=None):
    d = {"name": name, "type": typ, "link": link}
    if wid:
        d["widget"] = {"name": wid}
    if label:
        d["label"] = label
    return d


def p_in(name, typ, link=None, shape=7, label=None):
    d = {"name": name, "type": typ, "link": link}
    if shape:
        d["shape"] = shape
    if label:
        d["label"] = label
    return d


def w_out(name, typ, links=None):
    return {"name": name, "type": typ, "links": links or []}


# ============================================================
# 区域 1: 一句话输入
# ============================================================
story = add_node("PrimitiveStringMultiline", [40, 40],
                 ["一个落魄书生在雨夜捡到一枚能穿越时空的古镜，他回到过去改变了命运，却发现镜中自己的脸越来越模糊。"],
                 title="① 一句话剧情", size=[340, 130], color="#322", bgcolor="#533")
node(story)["inputs"] = [w_in("value", "STRING", wid="value")]
node(story)["outputs"] = [w_out("STRING", "STRING")]

# ============================================================
# 区域 2: LLM 剧本导演
# ============================================================
from factory.prompts import SCRIPT_DIRECTOR_PROMPT

llm_loader = add_node("llama_cpp_model_loader", [60, 300],
                      ["Qwen3.5-9B-heretic.Q8_0.gguf", "mmproj-Qwen3.5-9B-Q8_0.gguf", "Qwen3.5", 8192, 512, 0, 0],
                      title="②a LLM模型")
node(llm_loader)["inputs"] = [
    w_in("model", "COMBO", wid="model"), w_in("mmproj", "COMBO", wid="mmproj"),
    w_in("chat_handler", "COMBO", wid="chat_handler"), w_in("n_ctx", "INT", wid="n_ctx"),
    w_in("vram_limit", "INT", wid="vram_limit"), w_in("image_min_tokens", "INT", wid="image_min_tokens"),
    w_in("image_max_tokens", "INT", wid="image_max_tokens")]
node(llm_loader)["outputs"] = [w_out("MODEL", "LLAMACPPMODEL")]

llm_params = add_node("llama_cpp_parameters", [60, 460],
                      [4096, 30, 0.9, 0.05, 1, 0.7, 1, 0, 1, 0, 0.1, 5, 0],
                      title="②b LLM参数")
node(llm_params)["inputs"] = [
    w_in("max_tokens", "INT", wid="max_tokens"), w_in("top_k", "INT", wid="top_k"),
    w_in("top_p", "FLOAT", wid="top_p"), w_in("min_p", "FLOAT", wid="min_p"),
    w_in("typical_p", "FLOAT", wid="typical_p"), w_in("temperature", "FLOAT", wid="temperature"),
    w_in("repeat_penalty", "FLOAT", wid="repeat_penalty"), w_in("frequency_penalty", "FLOAT", wid="frequency_penalty"),
    w_in("presence_penalty", "FLOAT", wid="presence_penalty"), w_in("mirostat_mode", "INT", wid="mirostat_mode"),
    w_in("mirostat_eta", "FLOAT", wid="mirostat_eta"), w_in("mirostat_tau", "FLOAT", wid="mirostat_tau"),
    w_in("state_uid", "INT", wid="state_uid")]
node(llm_params)["outputs"] = [w_out("PARAMS", "LLAMACPPARAMS")]

llm_director = add_node("llama_cpp_instruct_adv", [60, 640],
                        ["Empty - Nothing", "（一句话剧情将自动填入）", SCRIPT_DIRECTOR_PROMPT, "one by one", 24, 896,
                         281689583359164, False, False],
                        title="②c 短剧导演(剧本JSON)", size=[420, 250])
node(llm_director)["inputs"] = [
    p_in("llama_model", "LLAMACPPMODEL"), p_in("parameters", "LLAMACPPARAMS"),
    w_in("preset_prompt", "COMBO", wid="preset_prompt"),
    w_in("custom_prompt", "STRING", wid="custom_prompt"),
    w_in("system_prompt", "STRING", wid="system_prompt"),
    w_in("inference_mode", "COMBO", wid="inference_mode"),
    w_in("max_frames", "INT", wid="max_frames"),
    w_in("max_size", "INT", wid="max_size"),
    w_in("seed", "INT", wid="seed"),
    w_in("force_offload", "BOOLEAN", wid="force_offload"),
    w_in("save_states", "BOOLEAN", wid="save_states")]
node(llm_director)["outputs"] = [w_out("output", "STRING"), w_out("output_list", "STRING"), w_out("state_uid", "INT")]

show_text = add_node("ShowText|pysssss", [540, 640], ["（剧本预览）"],
                     title="②d 剧本预览", size=[300, 300], collapsed=True)
node(show_text)["inputs"] = [w_in("text", "STRING", wid="text")]

json_clean = add_node("RegexExtract", [540, 320], ["", "\\{[\\s\\S]*\\}", "First Match", True, False, True, 1],
                      title="②e 提取JSON块", size=[300, 60])
node(json_clean)["inputs"] = [
    w_in("string", "STRING", wid="string"), w_in("regex_pattern", "STRING", wid="regex_pattern"),
    w_in("mode", "COMBO", wid="mode"), w_in("case_insensitive", "BOOLEAN", wid="case_insensitive"),
    w_in("multiline", "BOOLEAN", wid="multiline"), w_in("dotall", "BOOLEAN", wid="dotall"),
    w_in("group_index", "INT", wid="group_index")]
node(json_clean)["outputs"] = [w_out("STRING", "STRING")]

json_parse = add_node("LoadJsonFromText", [540, 420], title="②f 剧本→JSON", size=[260, 80])
node(json_parse)["inputs"] = [p_in("data", "STRING")]
node(json_parse)["outputs"] = [w_out("JSON", "JSON")]

char_key = add_node("GetTextFromJson", [540, 520], ["character"], title="②g 角色定妆提示词", size=[220, 60])
node(char_key)["inputs"] = [p_in("json", "JSON"), w_in("key", "STRING", wid="key")]
node(char_key)["outputs"] = [w_out("STRING", "STRING")]

# ============================================================
# 区域 3: 角色定妆图 (Z-Image)
# ============================================================
z_clip = add_node("CLIPLoader", [40, 1000], ["qwen_3_4b.safetensors", "lumina2", "default"],
                  title="③a Z-Image CLIP", size=[260, 90])
node(z_clip)["inputs"] = [w_in("clip_name", "COMBO", wid="clip_name"), w_in("type", "COMBO", wid="type"), w_in("device", "COMBO", wid="device")]
node(z_clip)["outputs"] = [w_out("CLIP", "CLIP")]

z_unet = add_node("UNETLoader", [340, 1000], ["z_image_turbo_bf16.safetensors", "default"],
                  title="③b Z-Image UNET", size=[260, 90])
node(z_unet)["inputs"] = [w_in("unet_name", "COMBO", wid="unet_name"), w_in("weight_dtype", "COMBO", wid="weight_dtype")]
node(z_unet)["outputs"] = [w_out("MODEL", "MODEL")]

z_vae = add_node("VAELoader", [640, 1000], ["ae.safetensors"], title="③c Z-Image VAE", size=[220, 90])
node(z_vae)["inputs"] = [w_in("vae_name", "COMBO", wid="vae_name")]
node(z_vae)["outputs"] = [w_out("VAE", "VAE")]

z_msa = add_node("ModelSamplingAuraFlow", [40, 1120], [3], title="③d AuraFlow", size=[200, 60])
node(z_msa)["inputs"] = [p_in("model", "MODEL"), w_in("shift", "FLOAT", wid="shift")]
node(z_msa)["outputs"] = [w_out("MODEL", "MODEL")]

z_enc = add_node("CLIPTextEncode", [40, 1220], ["（角色定妆提示词自动填入）"], title="③e 正提示", size=[220, 60])
node(z_enc)["inputs"] = [w_in("text", "STRING", wid="text"), p_in("clip", "CLIP")]
node(z_enc)["outputs"] = [w_out("CONDITIONING", "CONDITIONING")]

z_neg = add_node("ConditioningZeroOut", [40, 1320], title="③f 负提示", size=[200, 60])
node(z_neg)["inputs"] = [p_in("conditioning", "CONDITIONING")]
node(z_neg)["outputs"] = [w_out("CONDITIONING", "CONDITIONING")]

z_lat = add_node("EmptySD3LatentImage", [40, 1420], [1024, 1024, 1], title="③g 潜空间", size=[200, 60])
node(z_lat)["inputs"] = [w_in("width", "INT", wid="width"), w_in("height", "INT", wid="height"), w_in("batch_size", "INT", wid="batch_size")]
node(z_lat)["outputs"] = [w_out("LATENT", "LATENT")]

z_ks = add_node("KSampler", [40, 1520], [123456789, "randomize", 8, 1.0, "res_multistep", "simple", 1.0],
                title="③h Z-Image采样", size=[200, 60])
node(z_ks)["inputs"] = [
    p_in("model", "MODEL"), p_in("positive", "CONDITIONING"), p_in("negative", "CONDITIONING"), p_in("latent_image", "LATENT"),
    w_in("seed", "INT", wid="seed"), w_in("steps", "INT", wid="steps"), w_in("cfg", "FLOAT", wid="cfg"),
    w_in("sampler_name", "COMBO", wid="sampler_name"), w_in("scheduler", "COMBO", wid="scheduler"), w_in("denoise", "FLOAT", wid="denoise")]
node(z_ks)["outputs"] = [w_out("LATENT", "LATENT")]

z_dec = add_node("VAEDecode", [40, 1620], title="③i 定妆图解码（共用）", size=[220, 60], color="#235")
node(z_dec)["inputs"] = [p_in("samples", "LATENT"), p_in("vae", "VAE")]
node(z_dec)["outputs"] = [w_out("IMAGE", "IMAGE")]

# ============================================================
# 区域 4: H3 模型（共享）
# ============================================================
h3_clip = add_node("CLIPLoader", [40, 1800], ["qwen3vl_32b_h3_ultra_uncensored_heretic_int8_convrot.safetensors", "minimax", "default"],
                   title="④a H3 CLIP", size=[300, 90])
node(h3_clip)["inputs"] = [w_in("clip_name", "COMBO", wid="clip_name"), w_in("type", "COMBO", wid="type"), w_in("device", "COMBO", wid="device")]
node(h3_clip)["outputs"] = [w_out("CLIP", "CLIP")]

h3_vae = add_node("VAELoader", [360, 1800], ["minimax_h3_video_vae_fp16.safetensors"], title="④b H3 视频VAE", size=[250, 90])
node(h3_vae)["inputs"] = [w_in("vae_name", "COMBO", wid="vae_name")]
node(h3_vae)["outputs"] = [w_out("VAE", "VAE")]

h3_avae = add_node("VAELoader", [640, 1800], ["minimax_h3_audio_vae_fp32.safetensors"], title="④c H3 音频VAE", size=[250, 90])
node(h3_avae)["inputs"] = [w_in("vae_name", "COMBO", wid="vae_name")]
node(h3_avae)["outputs"] = [w_out("VAE", "VAE")]

h3_unet = add_node("UNETLoader", [920, 1800], ["minimax_h3_ref2va_pruned_int8_convrot.safetensors", "default"],
                   title="④d H3 UNET", size=[300, 90])
node(h3_unet)["inputs"] = [w_in("unet_name", "COMBO", wid="unet_name"), w_in("weight_dtype", "COMBO", wid="weight_dtype")]
node(h3_unet)["outputs"] = [w_out("MODEL", "MODEL")]

h3_sage = add_node("PathchSageAttentionKJ", [1260, 1800], ["sageattn_qk_int8_pv_fp8_cuda++", True],
                   title="④e 注意力优化", size=[280, 90])
node(h3_sage)["inputs"] = [p_in("model", "MODEL"), w_in("sage_attention", "COMBO", wid="sage_attention"), w_in("allow_compile", "BOOLEAN", wid="allow_compile")]
node(h3_sage)["outputs"] = [w_out("MODEL", "MODEL")]

h3_speed = add_node("TESpeedMiniMaxH3", [1580, 1800], [1, 0.1, 0.9, 2, "gpu"], title="④f 加速", size=[260, 90])
node(h3_speed)["inputs"] = [
    p_in("model", "MODEL"), w_in("processing_control_value", "INT", wid="processing_control_value"),
    w_in("processing_percent_1", "FLOAT", wid="processing_percent_1"), w_in("processing_percent_2", "FLOAT", wid="processing_percent_2"),
    w_in("mcs", "INT", wid="mcs"), w_in("device", "COMBO", wid="device")]
node(h3_speed)["outputs"] = [w_out("MODEL", "MODEL")]

res = add_node("ResolutionSelector", [40, 1920], ["9:16 (Portrait Widescreen)", 0.4, 32],
               title="④g 分辨率(共用)", size=[220, 130])
node(res)["inputs"] = [w_in("aspect_ratio", "COMBO", wid="aspect_ratio"), w_in("megapixels", "FLOAT", wid="megapixels"), w_in("multiple", "INT", wid="multiple")]
node(res)["outputs"] = [w_out("width", "INT"), w_out("height", "INT")]

prefix = add_node("PrimitiveString", [280, 1920], ["<Picture 1>: "], title="④h 参考图标签", size=[180, 60])
node(prefix)["inputs"] = [w_in("value", "STRING", wid="value")]
node(prefix)["outputs"] = [w_out("STRING", "STRING")]

# ============================================================
# 区域 5: 逐镜头 H3 ref2va
# ============================================================
COLS = 4
COL_X = [40, 380, 720, 1060]
ROW_Y = [2050, 4600]
shot_ids = []

for i in range(N_SHOTS):
    col = i % COLS
    row = i // COLS
    x = COL_X[col]
    y = ROW_Y[row]
    b = 200 + i * 20

    def add_shot_node(t, dx, dy, widgets, title, size=None):
        return add_node(t, [x + dx, y + dy], widgets, title=title.format(i + 1), size=size)

    obj = add_shot_node("GetObjectFromJson", 0, 0, ["shots.%d" % i], "镜头{} 对象")
    node(obj)["inputs"] = [p_in("json", "JSON"), w_in("key", "STRING", wid="key")]
    node(obj)["outputs"] = [w_out("JSON", "JSON")]

    vid = add_shot_node("GetTextFromJson", 0, 100, ["video_prompt"], "镜头{} 视频提示词")
    node(vid)["inputs"] = [p_in("json", "JSON"), w_in("key", "STRING", wid="key")]
    node(vid)["outputs"] = [w_out("STRING", "STRING")]

    dlg = add_shot_node("GetTextFromJson", 0, 200, ["dialogue"], "镜头{} 对白")
    node(dlg)["inputs"] = [p_in("json", "JSON"), w_in("key", "STRING", wid="key")]
    node(dlg)["outputs"] = [w_out("STRING", "STRING")]

    dur = add_shot_node("GetTextFromJson", 0, 300, ["duration"], "镜头{} 时长文本")
    node(dur)["inputs"] = [p_in("json", "JSON"), w_in("key", "STRING", wid="key")]
    node(dur)["outputs"] = [w_out("STRING", "STRING")]

    dur_regex = add_shot_node("RegexExtract", 0, 400, ["", "(\\d+\\.?\\d*)", "First Match", True, False, True, 0], "镜头{} 时长提取")
    node(dur_regex)["inputs"] = [
        w_in("string", "STRING", wid="string"), w_in("regex_pattern", "STRING", wid="regex_pattern"),
        w_in("mode", "COMBO", wid="mode"), w_in("case_insensitive", "BOOLEAN", wid="case_insensitive"),
        w_in("multiline", "BOOLEAN", wid="multiline"), w_in("dotall", "BOOLEAN", wid="dotall"),
        w_in("group_index", "INT", wid="group_index")]
    node(dur_regex)["outputs"] = [w_out("STRING", "STRING")]

    dur_conv = add_shot_node("easy convertAnything", 0, 500, ["float"], "镜头{} 时长转浮点")
    node(dur_conv)["inputs"] = [p_in("*", "*"), w_in("output_type", "COMBO", wid="output_type")]
    node(dur_conv)["outputs"] = [w_out("*", "*")]

    frames = add_shot_node("ComfyMathExpression", 0, 600,
                           ["min(124, max(5, round(a * 24)) + (5 - (max(5, round(a * 24)) % 17)) % 17)"],
                           "镜头{} 帧数", size=[230, 60])
    node(frames)["inputs"] = [p_in("values.a", "FLOAT,INT,BOOLEAN", label="a"), w_in("expression", "STRING", wid="expression")]
    node(frames)["outputs"] = [w_out("FLOAT", "FLOAT"), w_out("INT", "INT")]

    join1 = add_shot_node("JoinStrings", 0, 700, [" "], "镜头{} 提示词①", size=[220, 80])
    node(join1)["inputs"] = [p_in("string1", "STRING"), p_in("string2", "STRING"), w_in("delimiter", "STRING", wid="delimiter")]
    node(join1)["outputs"] = [w_out("STRING", "STRING")]

    join2 = add_shot_node("JoinStrings", 0, 800, ["\nDialogue: "], "镜头{} 提示词②", size=[220, 80])
    node(join2)["inputs"] = [p_in("string1", "STRING"), p_in("string2", "STRING"), w_in("delimiter", "STRING", wid="delimiter")]
    node(join2)["outputs"] = [w_out("STRING", "STRING")]

    ref = add_shot_node("MiniMaxH3ReferenceToVideo", 0, 900, ["", 960, 544, 124, "match"], "镜头{} ref2va", size=[300, 220])
    node(ref)["inputs"] = [
        p_in("clip", "CLIP"), p_in("vae", "VAE"), p_in("audio_vae", "VAE"),
        p_in("ref_images.ref_image_0", "IMAGE", label="ref_image_0"),
        w_in("prompt", "STRING", wid="prompt"),
        w_in("width", "INT", wid="width"), w_in("height", "INT", wid="height"),
        w_in("length", "INT", wid="length"), w_in("ref_image_size", "COMBO", wid="ref_image_size")]
    node(ref)["outputs"] = [w_out("positive", "CONDITIONING"), w_out("LATENT", "LATENT")]

    guider = add_shot_node("BasicGuider", 0, 1240, None, "镜头{} 引导")
    node(guider)["inputs"] = [p_in("model", "MODEL"), p_in("conditioning", "CONDITIONING")]
    node(guider)["outputs"] = [w_out("GUIDER", "GUIDER")]

    sched = add_shot_node("BasicScheduler", 0, 1340, ["simple", 16, 1.0], "镜头{} 调度")
    node(sched)["inputs"] = [p_in("model", "MODEL"), w_in("scheduler", "COMBO", wid="scheduler"), w_in("steps", "INT", wid="steps"), w_in("denoise", "FLOAT", wid="denoise")]
    node(sched)["outputs"] = [w_out("SIGMAS", "SIGMAS")]

    noise = add_shot_node("RandomNoise", 0, 1440, [440862999467967 + i, "randomize"], "镜头{} 噪声")
    node(noise)["inputs"] = [w_in("noise_seed", "INT", wid="noise_seed")]
    node(noise)["outputs"] = [w_out("NOISE", "NOISE")]

    ksel = add_shot_node("KSamplerSelect", 0, 1540, ["euler"], "镜头{} 采样器")
    node(ksel)["inputs"] = [w_in("sampler_name", "COMBO", wid="sampler_name")]
    node(ksel)["outputs"] = [w_out("SAMPLER", "SAMPLER")]

    sca = add_shot_node("SamplerCustomAdvanced", 0, 1640, None, "镜头{} 高级采样")
    node(sca)["inputs"] = [p_in("noise", "NOISE"), p_in("guider", "GUIDER"), p_in("sampler", "SAMPLER"), p_in("sigmas", "SIGMAS"), p_in("latent_image", "LATENT")]
    node(sca)["outputs"] = [w_out("LATENT", "LATENT")]

    vdec = add_shot_node("VAEDecode", 0, 1740, None, "镜头{} 视频解码")
    node(vdec)["inputs"] = [p_in("samples", "LATENT"), p_in("vae", "VAE")]
    node(vdec)["outputs"] = [w_out("IMAGE", "IMAGE")]

    adec = add_shot_node("VAEDecodeAudio", 0, 1840, None, "镜头{} 音频解码")
    node(adec)["inputs"] = [p_in("samples", "LATENT"), p_in("vae", "VAE")]
    node(adec)["outputs"] = [w_out("AUDIO", "AUDIO")]

    create = add_shot_node("CreateVideo", 0, 1940, [24, 8], "镜头{} 合成视频")
    node(create)["inputs"] = [p_in("images", "IMAGE"), p_in("audio", "AUDIO"), w_in("fps", "INT", wid="fps"), w_in("bit_depth", "INT", wid="bit_depth")]
    node(create)["outputs"] = [w_out("VIDEO", "VIDEO")]

    save = add_shot_node("SaveVideo", 0, 2040, ["drama_factory_shot_%d" % (i + 1), "mp4", "auto"], "镜头{} 保存片段")
    node(save)["inputs"] = [p_in("video", "VIDEO"), w_in("filename_prefix", "STRING", wid="filename_prefix"), w_in("format", "COMBO", wid="format"), w_in("codec", "COMBO", wid="codec")]

    shot_ids.append({"obj": obj, "vid": vid, "dlg": dlg, "dur": dur,
                     "dur_regex": dur_regex, "dur_conv": dur_conv, "frames": frames,
                     "join1": join1, "join2": join2, "ref": ref, "guider": guider,
                     "sched": sched, "noise": noise, "ksel": ksel, "sca": sca,
                     "vdec": vdec, "adec": adec, "create": create, "save": save})

# ============================================================
# 区域 6: 拼接
# ============================================================
merge_y = 2000
merge_nodes = []
for i in range(N_SHOTS - 1):
    m = add_node("easy mergeVideos", [40 + i * 240, merge_y], None, title="⑥ 合并镜头1-%d" % (i + 2))
    node(m)["inputs"] = [p_in("video_1", "VIDEO"), p_in("video_2", "VIDEO")]
    node(m)["outputs"] = [w_out("VIDEO", "VIDEO")]
    merge_nodes.append(m)

final = add_node("SaveVideo", [40 + (N_SHOTS - 1) * 240, merge_y], ["final_drama", "mp4", "auto"],
                 title="⑦ 完整短剧", size=[220, 60])
node(final)["inputs"] = [p_in("video", "VIDEO"), w_in("filename_prefix", "STRING", wid="filename_prefix"), w_in("format", "COMBO", wid="format"), w_in("codec", "COMBO", wid="codec")]


# ============================================================
# 连线
# ============================================================
def main_connect():
    # 一句话 -> 剧本
    connect(story, 0, llm_director, "custom_prompt", "STRING")
    connect(llm_loader, 0, llm_director, "llama_model", "LLAMACPPMODEL")
    connect(llm_params, 0, llm_director, "parameters", "LLAMACPPARAMS")
    connect(llm_director, 0, show_text, 0, "STRING")
    connect(llm_director, 0, json_clean, 0, "STRING")
    connect(json_clean, 0, json_parse, 0, "STRING")

    # character -> 定妆图
    connect(json_parse, 0, char_key, 0, "JSON")
    connect(char_key, 0, z_enc, 0, "STRING")

    # Z-Image 定妆图链
    connect(z_unet, 0, z_msa, 0, "MODEL")
    connect(z_msa, 0, z_ks, 0, "MODEL")
    connect(z_clip, 0, z_enc, 1, "CLIP")
    connect(z_enc, 0, z_ks, 1, "CONDITIONING")
    connect(z_enc, 0, z_neg, 0, "CONDITIONING")
    connect(z_neg, 0, z_ks, 2, "CONDITIONING")
    connect(z_lat, 0, z_ks, 3, "LATENT")
    connect(z_ks, 0, z_dec, 0, "LATENT")
    connect(z_vae, 0, z_dec, 1, "VAE")

    # H3 模型链
    connect(h3_unet, 0, h3_sage, 0, "MODEL")
    connect(h3_sage, 0, h3_speed, 0, "MODEL")

    # 逐镜头
    for i, s in enumerate(shot_ids):
        connect(json_parse, 0, s["obj"], 0, "JSON")
        connect(s["obj"], 0, s["vid"], 0, "JSON")
        connect(s["obj"], 0, s["dlg"], 0, "JSON")
        connect(s["obj"], 0, s["dur"], 0, "JSON")

        # 时长 -> 帧数
        connect(s["dur"], 0, s["dur_regex"], 0, "STRING")
        connect(s["dur_regex"], 0, s["dur_conv"], 0, "*")
        connect(s["dur_conv"], 0, s["frames"], 0, "FLOAT,INT,BOOLEAN")

        # prompt 拼接：<Picture 1>: + video_prompt + Dialogue: 对白
        connect(prefix, 0, s["join1"], "string1", "STRING")
        connect(s["vid"], 0, s["join1"], "string2", "STRING")
        connect(s["join1"], 0, s["join2"], "string1", "STRING")
        connect(s["dlg"], 0, s["join2"], "string2", "STRING")

        # ref2va
        connect(h3_clip, 0, s["ref"], "clip", "CLIP")
        connect(h3_vae, 0, s["ref"], "vae", "VAE")
        connect(h3_avae, 0, s["ref"], "audio_vae", "VAE")
        connect(z_dec, 0, s["ref"], "ref_images.ref_image_0", "IMAGE")  # 共用定妆图
        connect(s["join2"], 0, s["ref"], "prompt", "STRING")
        connect(res, 0, s["ref"], "width", "INT")
        connect(res, 1, s["ref"], "height", "INT")
        connect(s["frames"], 1, s["ref"], "length", "INT")

        # 采样链
        connect(h3_speed, 0, s["guider"], 0, "MODEL")
        connect(s["ref"], 0, s["guider"], 1, "CONDITIONING")
        connect(h3_speed, 0, s["sched"], 0, "MODEL")
        connect(s["guider"], 0, s["sca"], 1, "GUIDER")
        connect(s["sched"], 0, s["sca"], 3, "SIGMAS")
        connect(s["noise"], 0, s["sca"], 0, "NOISE")
        connect(s["ksel"], 0, s["sca"], 2, "SAMPLER")
        connect(s["ref"], 1, s["sca"], 4, "LATENT")

        # 解码 + 合成 + 保存
        connect(s["sca"], 0, s["vdec"], 0, "LATENT")
        connect(h3_vae, 0, s["vdec"], 1, "VAE")
        connect(s["sca"], 0, s["adec"], 0, "LATENT")
        connect(h3_avae, 0, s["adec"], 1, "VAE")
        connect(s["vdec"], 0, s["create"], 0, "IMAGE")
        connect(s["adec"], 0, s["create"], 1, "AUDIO")
        connect(s["create"], 0, s["save"], 0, "VIDEO")

    # 拼接链
    prev = shot_ids[0]["create"]
    for idx, m in enumerate(merge_nodes, start=1):
        connect(prev, 0, m, 0, "VIDEO")
        connect(shot_ids[idx]["create"], 0, m, 1, "VIDEO")
        prev = m
    connect(prev, 0, final, 0, "VIDEO")


def build():
    main_connect()
    wf = {
        "last_node_id": max(n["id"] for n in NODES),
        "last_link_id": max(l[0] for l in LINKS),
        "nodes": NODES,
        "links": LINKS,
        "groups": [
            {"title": "① 一句话输入", "bounding": [20, 20, 400, 160], "color": "#333"},
            {"title": "② LLM 剧本导演", "bounding": [20, 280, 820, 620], "color": "#3f2d20"},
            {"title": "③ 角色定妆图 (Z-Image)", "bounding": [20, 980, 800, 700], "color": "#2d1f3a"},
            {"title": "④ H3 模型 (共享)", "bounding": [20, 1780, 1920, 300], "color": "#1f3a2d"},
            {"title": "⑤ 逐镜头 H3 ref2va (共用定妆图)", "bounding": [20, 2030, 1340, 3600], "color": "#3a2d1f"},
            {"title": "⑥ 拼接输出", "bounding": [20, 1980, 1920, 120], "color": "#2d3a1f"},
        ],
        "config": {},
        "extra": {"ds": {"scale": 0.5, "offset": [0, 0]}},
        "version": 0.4,
    }
    return wf


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    wf = build()
    with open(DST, "w", encoding="utf-8") as f:
        json.dump(wf, f, ensure_ascii=False, indent=1)
    print(f"生成工作流：{DST}")
    print(f"  节点数：{len(NODES)}，连线数：{len(LINKS)}，镜头数：{N_SHOTS}")
