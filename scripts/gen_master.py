"""Generate the master short-drama pipeline workflow JSON for ComfyUI canvas.
一句话 -> LLM剧本(4镜头) -> 每镜头Z-Image参考图 -> 每镜头H3视频 -> 拼接 -> 完整短剧

Canvas format: nodes with inputs/outputs/links/widgets_values, plus a links array.
"""
import json

SCRIPT_PROMPT = """你是短剧导演兼编剧。用户会给你一句话故事梗概，你要把它扩写成一部完整的短剧分镜剧本。

严格输出 JSON（不要输出任何其他文字、markdown、代码块标记、注释或解释），格式如下：
{
  "title": "短剧标题",
  "shots": [
    {
      "shot": 1,
      "scene": "场景描述（如：夜晚的古城街道）",
      "image_prompt": "用于AI生成该镜头关键帧图的完整绘图提示词，包含主体、场景、光线、构图、风格",
      "dialogue": "该镜头角色对白或旁白（用于AI生成配音和画面提示）",
      "video_prompt": "用于AI视频生成的镜头运动描述，如镜头语言、动作、运镜方向",
      "duration": 5
    }
  ]
}

硬性要求（必须严格遵守）：
- 共 4 个镜头（shot 1-4）
- 每个镜头的 image_prompt 要独立成画，角色保持一致
- duration 每镜头 5 秒
- 对白要口语化、有戏剧冲突
- 输出的必须是合法 JSON：所有字符串用双引号，禁止单引号，禁止尾随逗号，禁止注释，禁止缩进多余字符
- 第一行直接以 { 开始，最后一行以 } 结束，不要输出 ```json 或 ``` 之类代码块标记
- 对白中的引号一律使用中文引号「」或省略，不要使用英文单引号
"""

# 正则：提取文本中第一个 {...} 到最后一个 } 之间的 JSON 块（容错 LLM 输出的 markdown/前后缀文字）
JSON_EXTRACT_RE = "\\{[\\s\\S]*\\}"

NODES = []
LINKS = []
_nid = 100
_lid = 5000


def add_node(node_type, pos, widgets=None, title=None, size=None, collapsed=False,
             color=None, bgcolor=None, mode=0):
    global _nid
    n = {
        "id": _nid, "type": node_type,
        "pos": list(pos), "size": size or [200, 100],
        "flags": {"collapsed": collapsed} if collapsed else {},
        "order": len(NODES), "mode": mode,
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


# ---------------- link helpers ----------------
def connect(src_id, src_slot, dst_id, dst_slot, typ):
    global _lid
    link_id = _lid
    _lid += 1
    LINKS.append([link_id, src_id, src_slot, dst_id, dst_slot, typ])
    # dst_slot is input index; record link in dst input
    ins = node(dst_id)["inputs"]
    if isinstance(dst_slot, int) and dst_slot < len(ins):
        ins[dst_slot]["link"] = link_id
    elif isinstance(dst_slot, str):
        for inp in ins:
            if inp["name"] == dst_slot:
                inp["link"] = link_id
    # record link in src output (index)
    outs = node(src_id)["outputs"]
    if isinstance(src_slot, int) and src_slot < len(outs):
        outs[src_slot].setdefault("links", []).append(link_id)
    elif isinstance(src_slot, str):
        for out in outs:
            if out["name"] == src_slot:
                out.setdefault("links", []).append(link_id)


def node(nid):
    return next(n for n in NODES if n["id"] == nid)


def w_in(name, typ, wid=None, link=None, label=None, lname=None):
    d = {"name": name, "type": typ, "link": link}
    if wid:
        d["widget"] = {"name": wid}
    if label:
        d["label"] = label
    if lname:
        d["localized_name"] = lname
    return d


def p_in(name, typ, link=None, shape=7, label=None, lname=None):
    d = {"name": name, "type": typ, "link": link}
    if shape:
        d["shape"] = shape
    if label:
        d["label"] = label
    if lname:
        d["localized_name"] = lname
    return d


def w_out(name, typ, links=None, label=None, lname=None):
    d = {"name": name, "type": typ, "links": links or []}
    if label:
        d["label"] = label
    if lname:
        d["localized_name"] = lname
    return d


# ============================================================
# 区域 1: 一句话输入
# ============================================================
story = add_node("PrimitiveStringMultiline", [40, 40],
                 ["一个落魄书生在雨夜捡到一枚能穿越时空的古镜，他回到过去改变了命运，却发现镜中自己的脸越来越模糊。"],
                 title="① 一句话剧情", size=[330, 130], color="#322", bgcolor="#533")
node(story)["inputs"] = [w_in("value", "STRING", wid="value")]
node(story)["outputs"] = [w_out("STRING", "STRING", label="字符串")]

# ============================================================
# 区域 2: LLM 剧本导演
# ============================================================
llm_loader = add_node("llama_cpp_model_loader", [60, 300],
                      ["Qwen3.5-9B-heretic.Q8_0.gguf", "mmproj-Qwen3.5-9B-Q8_0.gguf", "Qwen3.5", 8064, -1, 0, 0],
                      title="②a LLM模型")
node(llm_loader)["inputs"] = [
    w_in("model", "COMBO", wid="model"), w_in("mmproj", "COMBO", wid="mmproj"),
    w_in("chat_handler", "COMBO", wid="chat_handler"), w_in("n_ctx", "INT", wid="n_ctx"),
    w_in("vram_limit", "INT", wid="vram_limit"), w_in("image_min_tokens", "INT", wid="image_min_tokens"),
    w_in("image_max_tokens", "INT", wid="image_max_tokens"),
]
node(llm_loader)["outputs"] = [w_out("MODEL", "LLAMACPPMODEL")]

llm_params = add_node("llama_cpp_parameters", [60, 460],
                      [1024, 30, 0.9, 0.05, 1, 0.8, 1, 0, 1, 0, 0.1, 5, 0],
                      title="②b LLM参数")
node(llm_params)["inputs"] = [
    w_in("max_tokens", "INT", wid="max_tokens"), w_in("top_k", "INT", wid="top_k"),
    w_in("top_p", "FLOAT", wid="top_p"), w_in("min_p", "FLOAT", wid="min_p"),
    w_in("typical_p", "FLOAT", wid="typical_p"), w_in("temperature", "FLOAT", wid="temperature"),
    w_in("repeat_penalty", "FLOAT", wid="repeat_penalty"), w_in("frequency_penalty", "FLOAT", wid="frequency_penalty"),
    w_in("presence_penalty", "FLOAT", wid="presence_penalty"), w_in("mirostat_mode", "INT", wid="mirostat_mode"),
    w_in("mirostat_eta", "FLOAT", wid="mirostat_eta"), w_in("mirostat_tau", "FLOAT", wid="mirostat_tau"),
    w_in("state_uid", "INT", wid="state_uid"),
]
node(llm_params)["outputs"] = [w_out("PARAMS", "LLAMACPPARAMS")]

llm_director = add_node("llama_cpp_instruct_adv", [60, 640],
                        ["Normal - Describe", "（一句话剧情将自动填入）", SCRIPT_PROMPT, "images", 24, 896,
                         281689583359164, "randomize", False, False],
                        title="②c 短剧导演(剧本JSON)", size=[420, 250])
# custom_prompt 是可连接 widget：从 story 连接，填入用户的一句话
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
    w_in("save_states", "BOOLEAN", wid="save_states"),
]
node(llm_director)["outputs"] = [w_out("output", "STRING"), w_out("output_list", "STRING"), w_out("state_uid", "INT")]

show_text = add_node("ShowText|pysssss", [540, 640], ["（剧本预览）"],
                     title="②d 剧本预览",
                     size=[300, 300], collapsed=True)
node(show_text)["inputs"] = [w_in("text", "STRING", wid="text")]

# LLM 输出经 RegexExtract 提取 {...} JSON 块（容错 markdown code fence / 前后缀文字）
json_clean = add_node("RegexExtract", [540, 320], ["", JSON_EXTRACT_RE, "First Match", True, False, True, 1],
                      title="②e 提取JSON块", size=[300, 60])
node(json_clean)["inputs"] = [
    w_in("string", "STRING", wid="string"), w_in("regex_pattern", "STRING", wid="regex_pattern"),
    w_in("mode", "COMBO", wid="mode"), w_in("case_insensitive", "BOOLEAN", wid="case_insensitive"),
    w_in("multiline", "BOOLEAN", wid="multiline"), w_in("dotall", "BOOLEAN", wid="dotall"),
    w_in("group_index", "INT", wid="group_index"),
]
node(json_clean)["outputs"] = [w_out("STRING", "STRING")]

json_parse = add_node("LoadJsonFromText", [540, 420], title="②f 剧本→JSON", size=[260, 80])
node(json_parse)["inputs"] = [p_in("data", "STRING")]
node(json_parse)["outputs"] = [w_out("JSON", "JSON")]

# ============================================================
# 区域 3: 剧本分发 (4 镜头)
# ============================================================
N_SHOTS = 4
shot_obj = []
for i in range(N_SHOTS):
    col = 40 + i * 330
    o = add_node("GetObjectFromJson", [col, 900], ["shots.%d" % i],
                 title="镜头%d 对象" % (i + 1), size=[200, 60])
    node(o)["inputs"] = [p_in("json", "JSON"), w_in("key", "STRING", wid="key")]
    node(o)["outputs"] = [w_out("JSON", "JSON")]

    ip = add_node("GetTextFromJson", [col, 1000], ["image_prompt"],
                  title="镜头%d 画面提示词" % (i + 1), size=[200, 60])
    node(ip)["inputs"] = [p_in("json", "JSON"), w_in("key", "STRING", wid="key")]
    node(ip)["outputs"] = [w_out("STRING", "STRING")]

    vp = add_node("GetTextFromJson", [col, 1080], ["video_prompt"],
                  title="镜头%d 视频提示词" % (i + 1), size=[200, 60])
    node(vp)["inputs"] = [p_in("json", "JSON"), w_in("key", "STRING", wid="key")]
    node(vp)["outputs"] = [w_out("STRING", "STRING")]

    dl = add_node("GetTextFromJson", [col, 1160], ["dialogue"],
                  title="镜头%d 对白" % (i + 1), size=[200, 60])
    node(dl)["inputs"] = [p_in("json", "JSON"), w_in("key", "STRING", wid="key")]
    node(dl)["outputs"] = [w_out("STRING", "STRING")]

    shot_obj.append({"obj": o, "img": ip, "vid": vp, "dlg": dl})

# ============================================================
# 区域 4: Z-Image 图生成 (共享模型)
# ============================================================
zclip = add_node("CLIPLoader", [40, 1300],
                 ["qwen_3_4b.safetensors", "lumina2", "default"],
                 title="④a Z-Image CLIP", size=[260, 90])
node(zclip)["inputs"] = [
    w_in("clip_name", "COMBO", wid="clip_name"), w_in("type", "COMBO", wid="type"),
    w_in("device", "COMBO", wid="device"),
]
node(zclip)["outputs"] = [w_out("CLIP", "CLIP")]

zunet = add_node("UNETLoader", [340, 1300],
                 ["z_image_turbo_bf16.safetensors", "default"],
                 title="④b Z-Image UNET", size=[260, 90])
node(zunet)["inputs"] = [w_in("unet_name", "COMBO", wid="unet_name"), w_in("weight_dtype", "COMBO", wid="weight_dtype")]
node(zunet)["outputs"] = [w_out("MODEL", "MODEL")]

zvae = add_node("VAELoader", [640, 1300],
                ["ae.safetensors"],
                title="④c Z-Image VAE", size=[220, 90])
node(zvae)["inputs"] = [w_in("vae_name", "COMBO", wid="vae_name")]
node(zvae)["outputs"] = [w_out("VAE", "VAE")]

z_shots = []
for i in range(N_SHOTS):
    col = 40 + i * 330
    row = 1450
    msa = add_node("ModelSamplingAuraFlow", [col, row], [3],
                   title="镜头%d AuraFlow" % (i + 1), size=[200, 60])
    node(msa)["inputs"] = [p_in("model", "MODEL"), w_in("shift", "FLOAT", wid="shift")]
    node(msa)["outputs"] = [w_out("MODEL", "MODEL")]

    enc = add_node("CLIPTextEncode", [col, row + 100],
                   ["（镜头画面提示词自动填入）"],
                   title="镜头%d 正提示" % (i + 1), size=[200, 60])
    node(enc)["inputs"] = [w_in("text", "STRING", wid="text"), p_in("clip", "CLIP")]
    node(enc)["outputs"] = [w_out("CONDITIONING", "CONDITIONING")]

    neg = add_node("ConditioningZeroOut", [col, row + 200],
                   title="镜头%d 负提示" % (i + 1), size=[200, 60])
    node(neg)["inputs"] = [p_in("conditioning", "CONDITIONING")]
    node(neg)["outputs"] = [w_out("CONDITIONING", "CONDITIONING")]

    lat = add_node("EmptySD3LatentImage", [col, row + 300], [1024, 1024, 1],
                   title="镜头%d 潜空间" % (i + 1), size=[200, 60])
    node(lat)["inputs"] = [
        w_in("width", "INT", wid="width"), w_in("height", "INT", wid="height"),
        w_in("batch_size", "INT", wid="batch_size"),
    ]
    node(lat)["outputs"] = [w_out("LATENT", "LATENT")]

    ks = add_node("KSampler", [col, row + 400],
                  [12345 + i, "randomize", 8, 1.0, "res_multistep", "simple", 1.0],
                  title="镜头%d Z-Image采样" % (i + 1), size=[200, 60])
    node(ks)["inputs"] = [
        p_in("model", "MODEL"), p_in("positive", "CONDITIONING"),
        p_in("negative", "CONDITIONING"), p_in("latent_image", "LATENT"),
        w_in("seed", "INT", wid="seed"), w_in("steps", "INT", wid="steps"),
        w_in("cfg", "FLOAT", wid="cfg"), w_in("sampler_name", "COMBO", wid="sampler_name"),
        w_in("scheduler", "COMBO", wid="scheduler"), w_in("denoise", "FLOAT", wid="denoise"),
    ]
    node(ks)["outputs"] = [w_out("LATENT", "LATENT")]

    dec = add_node("VAEDecode", [col, row + 500], title="镜头%d 解码" % (i + 1), size=[200, 60])
    node(dec)["inputs"] = [p_in("samples", "LATENT"), p_in("vae", "VAE")]
    node(dec)["outputs"] = [w_out("IMAGE", "IMAGE")]

    z_shots.append({"msa": msa, "enc": enc, "neg": neg, "lat": lat, "k": ks, "dec": dec})

# ============================================================
# 区域 5: H3 视频生成 (共享模型)
# ============================================================
hclip = add_node("CLIPLoader", [40, 2100],
                 ["qwen3vl_32b_h3_ultra_uncensored_heretic_int8_convrot.safetensors", "minimax", "default"],
                 title="⑤a H3 CLIP", size=[300, 90])
node(hclip)["inputs"] = [
    w_in("clip_name", "COMBO", wid="clip_name"), w_in("type", "COMBO", wid="type"),
    w_in("device", "COMBO", wid="device"),
]
node(hclip)["outputs"] = [w_out("CLIP", "CLIP")]

hvae = add_node("VAELoader", [360, 2100],
                ["minimax_h3_video_vae_fp16.safetensors"],
                title="⑤b H3 视频VAE", size=[250, 90])
node(hvae)["inputs"] = [w_in("vae_name", "COMBO", wid="vae_name")]
node(hvae)["outputs"] = [w_out("VAE", "VAE")]

havae = add_node("VAELoader", [640, 2100],
                 ["minimax_h3_audio_vae_fp32.safetensors"],
                 title="⑤c H3 音频VAE", size=[250, 90])
node(havae)["inputs"] = [w_in("vae_name", "COMBO", wid="vae_name")]
node(havae)["outputs"] = [w_out("VAE", "VAE")]

hunet = add_node("UNETLoader", [920, 2100],
                 ["minimax_h3_ref2va_pruned_int8_convrot.safetensors", "default"],
                 title="⑤d H3 UNET", size=[300, 90])
node(hunet)["inputs"] = [w_in("unet_name", "COMBO", wid="unet_name"), w_in("weight_dtype", "COMBO", wid="weight_dtype")]
node(hunet)["outputs"] = [w_out("MODEL", "MODEL")]

hsage = add_node("PathchSageAttentionKJ", [1260, 2100],
                 ["sageattn_qk_int8_pv_fp8_cuda++", True],
                 title="⑤e 注意力优化", size=[280, 90])
node(hsage)["inputs"] = [
    p_in("model", "MODEL"),
    w_in("sage_attention", "COMBO", wid="sage_attention"),
    w_in("allow_compile", "BOOLEAN", wid="allow_compile"),
]
node(hsage)["outputs"] = [w_out("MODEL", "MODEL")]

hspeed = add_node("TESpeedMiniMaxH3", [1580, 2100],
                  [1, 0.1, 0.9, 2, "gpu"],
                  title="⑤f 加速", size=[260, 90])
node(hspeed)["inputs"] = [
    p_in("model", "MODEL"),
    w_in("processing_control_value", "INT", wid="processing_control_value"),
    w_in("processing_percent_1", "FLOAT", wid="processing_percent_1"),
    w_in("processing_percent_2", "FLOAT", wid="processing_percent_2"),
    w_in("mcs", "INT", wid="mcs"),
    w_in("device", "COMBO", wid="device"),
]
node(hspeed)["outputs"] = [w_out("MODEL", "MODEL")]

h_shots = []
for i in range(N_SHOTS):
    col = 40 + i * 330
    row = 2250

    res = add_node("ResolutionSelector", [col, row],
                   ["16:9 (Widescreen)", 0.3, 32],
                   title="镜头%d 分辨率" % (i + 1), size=[220, 130])
    node(res)["inputs"] = [
        w_in("aspect_ratio", "COMBO", wid="aspect_ratio"),
        w_in("megapixels", "FLOAT", wid="megapixels"),
        w_in("multiple", "INT", wid="multiple"),
    ]
    node(res)["outputs"] = [w_out("width", "INT", label="宽度"), w_out("height", "INT", label="高度")]

    dur = add_node("PrimitiveFloat", [col, row + 150], [5.0],
                   title="镜头%d 时长(秒)" % (i + 1), size=[180, 90])
    node(dur)["inputs"] = [w_in("value", "FLOAT", wid="value")]
    node(dur)["outputs"] = [w_out("FLOAT", "FLOAT")]

    frames = add_node("ComfyMathExpression", [col, row + 260],
                      ["max(5, round(a * 24)) + (5 - (max(5, round(a * 24)) % 17)) % 17"],
                      title="镜头%d 帧数" % (i + 1), size=[225, 0], collapsed=True)
    node(frames)["inputs"] = [
        p_in("values.a", "FLOAT,INT,BOOLEAN", label="a", lname="values.a"),
        w_in("expression", "STRING", wid="expression"),
    ]
    node(frames)["outputs"] = [w_out("FLOAT", "FLOAT"), w_out("INT", "INT")]

    join = add_node("JoinStrings", [col, row + 380],
                    ["\n"], title="镜头%d H3提示词" % (i + 1), size=[220, 100])
    node(join)["inputs"] = [
        w_in("delimiter", "STRING", wid="delimiter"),
        p_in("string1", "STRING"), p_in("string2", "STRING"),
    ]
    node(join)["outputs"] = [w_out("STRING", "STRING")]

    ref = add_node("MiniMaxH3ReferenceToVideo", [col, row + 500],
                   ["", 960, 544, 124, "match"],
                   title="镜头%d H3参考视频" % (i + 1), size=[300, 220])
    node(ref)["inputs"] = [
        p_in("clip", "CLIP"), p_in("vae", "VAE"), p_in("audio_vae", "VAE"),
        p_in("ref_images.ref_image_0", "IMAGE", label="ref_image_0"),
        w_in("prompt", "STRING", wid="prompt"),
        w_in("width", "INT", wid="width"), w_in("height", "INT", wid="height"),
        w_in("length", "INT", wid="length"), w_in("ref_image_size", "COMBO", wid="ref_image_size"),
    ]
    node(ref)["outputs"] = [w_out("positive", "CONDITIONING"), w_out("LATENT", "LATENT")]

    guider = add_node("BasicGuider", [col, row + 740], title="镜头%d 引导" % (i + 1), size=[200, 60])
    node(guider)["inputs"] = [p_in("model", "MODEL"), p_in("conditioning", "CONDITIONING")]
    node(guider)["outputs"] = [w_out("GUIDER", "GUIDER")]

    sched = add_node("BasicScheduler", [col, row + 840],
                     ["simple", 16, 1.0],
                     title="镜头%d 调度" % (i + 1), size=[200, 60])
    node(sched)["inputs"] = [
        p_in("model", "MODEL"),
        w_in("scheduler", "COMBO", wid="scheduler"),
        w_in("steps", "INT", wid="steps"),
        w_in("denoise", "FLOAT", wid="denoise"),
    ]
    node(sched)["outputs"] = [w_out("SIGMAS", "SIGMAS")]

    noise = add_node("RandomNoise", [col, row + 940], [440862999467967 + i, "randomize"],
                     title="镜头%d 噪声" % (i + 1), size=[200, 60])
    node(noise)["inputs"] = [w_in("noise_seed", "INT", wid="noise_seed")]
    node(noise)["outputs"] = [w_out("NOISE", "NOISE")]

    ksel = add_node("KSamplerSelect", [col, row + 1040], ["euler"],
                    title="镜头%d 采样器" % (i + 1), size=[200, 60])
    node(ksel)["inputs"] = [w_in("sampler_name", "COMBO", wid="sampler_name")]
    node(ksel)["outputs"] = [w_out("SAMPLER", "SAMPLER")]

    sca = add_node("SamplerCustomAdvanced", [col, row + 1140],
                   title="镜头%d 高级采样" % (i + 1), size=[200, 60])
    node(sca)["inputs"] = [
        p_in("noise", "NOISE"), p_in("guider", "GUIDER"), p_in("sampler", "SAMPLER"),
        p_in("sigmas", "SIGMAS"), p_in("latent_image", "LATENT"),
    ]
    node(sca)["outputs"] = [w_out("LATENT", "LATENT")]

    vdec = add_node("VAEDecode", [col, row + 1240], title="镜头%d 视频解码" % (i + 1), size=[200, 60])
    node(vdec)["inputs"] = [p_in("samples", "LATENT"), p_in("vae", "VAE")]
    node(vdec)["outputs"] = [w_out("IMAGE", "IMAGE")]

    adec = add_node("VAEDecodeAudio", [col, row + 1340], title="镜头%d 音频解码" % (i + 1), size=[200, 60])
    node(adec)["inputs"] = [p_in("samples", "LATENT"), p_in("vae", "VAE")]
    node(adec)["outputs"] = [w_out("AUDIO", "AUDIO")]

    create = add_node("CreateVideo", [col, row + 1440], [24, 8],
                      title="镜头%d 合成视频" % (i + 1), size=[200, 60])
    node(create)["inputs"] = [
        p_in("images", "IMAGE"), p_in("audio", "AUDIO"),
        w_in("fps", "INT", wid="fps"), w_in("bit_depth", "INT", wid="bit_depth"),
    ]
    node(create)["outputs"] = [w_out("VIDEO", "VIDEO")]

    hsave = add_node("SaveVideo", [col, row + 1540],
                     ["drama_shot_%d" % (i + 1), "mp4", "auto"],
                     title="镜头%d 保存片段" % (i + 1), size=[200, 60])
    node(hsave)["inputs"] = [
        p_in("video", "VIDEO"),
        w_in("filename_prefix", "STRING", wid="filename_prefix"),
        w_in("format", "COMBO", wid="format"),
        w_in("codec", "COMBO", wid="codec"),
    ]

    h_shots.append({"res": res, "dur": dur, "frames": frames, "join": join, "ref": ref,
                    "guider": guider, "sched": sched, "noise": noise, "ksel": ksel,
                    "sca": sca, "vdec": vdec, "adec": adec, "create": create, "save": hsave})

# ============================================================
# 区域 6: 拼接 (easy mergeVideos 只支持2输入 -> 链式合并)
# ============================================================
merge_ab = add_node("easy mergeVideos", [40, 3850], title="⑥a 合并镜头1+2", size=[200, 60])
node(merge_ab)["inputs"] = [p_in("video_1", "VIDEO"), p_in("video_2", "VIDEO")]
node(merge_ab)["outputs"] = [w_out("VIDEO", "VIDEO")]

merge_cd = add_node("easy mergeVideos", [280, 3850], title="⑥b 合并镜头3+4", size=[200, 60])
node(merge_cd)["inputs"] = [p_in("video_1", "VIDEO"), p_in("video_2", "VIDEO")]
node(merge_cd)["outputs"] = [w_out("VIDEO", "VIDEO")]

merge_all = add_node("easy mergeVideos", [520, 3850], title="⑥c 合并AB+CD", size=[200, 60])
node(merge_all)["inputs"] = [p_in("video_1", "VIDEO"), p_in("video_2", "VIDEO")]
node(merge_all)["outputs"] = [w_out("VIDEO", "VIDEO")]

final = add_node("SaveVideo", [780, 3850], ["final_drama", "mp4", "auto"],
                 title="⑦ 完整短剧", size=[220, 60])
node(final)["inputs"] = [
    p_in("video", "VIDEO"),
    w_in("filename_prefix", "STRING", wid="filename_prefix"),
    w_in("format", "COMBO", wid="format"),
    w_in("codec", "COMBO", wid="codec"),
]


# ============================================================
# 连线
# ============================================================
def main_connect():
    connect(story, 0, llm_director, "custom_prompt", "STRING")  # 一句话 -> custom_prompt
    connect(llm_loader, 0, llm_director, "llama_model", "LLAMACPPMODEL")
    connect(llm_params, 0, llm_director, "parameters", "LLAMACPPARAMS")
    connect(llm_director, 0, show_text, 0, "STRING")
    connect(llm_director, 0, json_clean, 0, "STRING")
    connect(json_clean, 0, json_parse, 0, "STRING")

    for s in shot_obj:
        connect(json_parse, 0, s["obj"], 0, "JSON")
        connect(s["obj"], 0, s["img"], 0, "JSON")
        connect(s["obj"], 0, s["vid"], 0, "JSON")
        connect(s["obj"], 0, s["dlg"], 0, "JSON")

    for z in z_shots:
        connect(zunet, 0, z["msa"], 0, "MODEL")
        connect(z["msa"], 0, z["k"], 0, "MODEL")
        connect(zclip, 0, z["enc"], 1, "CLIP")
        connect(z["enc"], 0, z["k"], 1, "CONDITIONING")
        connect(z["enc"], 0, z["neg"], 0, "CONDITIONING")
        connect(z["neg"], 0, z["k"], 2, "CONDITIONING")
        connect(z["lat"], 0, z["k"], 3, "LATENT")
        connect(z["k"], 0, z["dec"], 0, "LATENT")
        connect(zvae, 0, z["dec"], 1, "VAE")

    connect(hunet, 0, hsage, 0, "MODEL")
    connect(hsage, 0, hspeed, 0, "MODEL")

    for i, (s, z, h) in enumerate(zip(shot_obj, z_shots, h_shots)):
        connect(s["img"], 0, z["enc"], 0, "STRING")
        connect(z["dec"], 0, h["ref"], 3, "IMAGE")
        connect(s["vid"], 0, h["join"], 1, "STRING")
        connect(s["dlg"], 0, h["join"], 2, "STRING")
        connect(h["join"], 0, h["ref"], 4, "STRING")
        connect(hclip, 0, h["ref"], 0, "CLIP")
        connect(hvae, 0, h["ref"], 1, "VAE")
        connect(havae, 0, h["ref"], 2, "VAE")
        connect(h["dur"], 0, h["frames"], 0, "FLOAT")
        connect(h["frames"], 1, h["ref"], 7, "INT")
        connect(h["res"], 0, h["ref"], 5, "INT")
        connect(h["res"], 1, h["ref"], 6, "INT")
        connect(hspeed, 0, h["guider"], 0, "MODEL")
        connect(h["ref"], 0, h["guider"], 1, "CONDITIONING")
        connect(hspeed, 0, h["sched"], 0, "MODEL")
        connect(h["guider"], 0, h["sca"], 1, "GUIDER")
        connect(h["sched"], 0, h["sca"], 3, "SIGMAS")
        connect(h["noise"], 0, h["sca"], 0, "NOISE")
        connect(h["ksel"], 0, h["sca"], 2, "SAMPLER")
        connect(h["ref"], 1, h["sca"], 4, "LATENT")
        connect(h["sca"], 0, h["vdec"], 0, "LATENT")
        connect(hvae, 0, h["vdec"], 1, "VAE")
        connect(h["sca"], 0, h["adec"], 0, "LATENT")
        connect(havae, 0, h["adec"], 1, "VAE")
        connect(h["vdec"], 0, h["create"], 0, "IMAGE")
        connect(h["adec"], 0, h["create"], 1, "AUDIO")
        connect(h["create"], 0, h["save"], 0, "VIDEO")
        if i == 0:
            connect(h["create"], 0, merge_ab, 0, "VIDEO")
        elif i == 1:
            connect(h["create"], 0, merge_ab, 1, "VIDEO")
        elif i == 2:
            connect(h["create"], 0, merge_cd, 0, "VIDEO")
        elif i == 3:
            connect(h["create"], 0, merge_cd, 1, "VIDEO")

    connect(merge_ab, 0, merge_all, 0, "VIDEO")
    connect(merge_cd, 0, merge_all, 1, "VIDEO")
    connect(merge_all, 0, final, 0, "VIDEO")


def build():
    main_connect()
    wf = {
        "last_node_id": max(n["id"] for n in NODES),
        "last_link_id": max(l[0] for l in LINKS),
        "nodes": NODES,
        "links": LINKS,
        "groups": [
            {"title": "① 一句话输入", "bounding": [20, 20, 400, 160], "color": "#333", "font_size": 20},
            {"title": "② LLM 剧本导演", "bounding": [20, 280, 620, 420], "color": "#3f2d20", "font_size": 20},
            {"title": "③ 剧本分发 (4镜头)", "bounding": [20, 880, 1340, 340], "color": "#1f3a2d", "font_size": 20},
            {"title": "④ Z-Image 镜头参考图生成", "bounding": [20, 1280, 1340, 760], "color": "#2d1f3a", "font_size": 20},
            {"title": "⑤ H3 镜头视频生成", "bounding": [20, 2080, 1340, 1780], "color": "#3a2d1f", "font_size": 20},
            {"title": "⑥ 拼接输出完整短剧", "bounding": [20, 3830, 620, 380], "color": "#2d3a1f", "font_size": 20},
        ],
        "config": {},
        "extra": {"ds": {"scale": 0.6, "offset": [0, 0]}},
        "version": 0.4,
    }
    return wf


if __name__ == "__main__":
    wf = build()
    # debug: verify H3 ref clip/vae links
    for h in h_shots:
        rn = node(h["ref"])
        linked = {i["name"]: i.get("link") for i in rn["inputs"] if i.get("link")}
        print(f"H3 ref node {h['ref']}: links={linked}")
    with open(r"D:\Comfyui\Comfyui\user\default\workflows\一句话短剧全自动流水线.json", "w", encoding="utf-8") as f:
        json.dump(wf, f, ensure_ascii=False, indent=1)
    print("Generated workflow:", len(NODES), "nodes,", len(LINKS), "links")
