# -*- coding: utf-8 -*-
"""Generate a 20-shot version of the short-drama pipeline from the 4-shot template.
Keeps shared nodes (input/LLM/JSON-clean/models/resolution) and clones the per-shot
template 20x. Chain-merges 20 shots into one final video.
"""
import json, copy, sys
sys.stdout.reconfigure(encoding="utf-8")

SRC = r"D:\Comfyui\.monkeycode\uploads\一句话短剧.json"
DST = r"D:\Comfyui\Comfyui\user\default\workflows\一句话短剧20镜头.json"

wf = json.load(open(SRC, encoding="utf-8"))
src = {n["id"]: n for n in wf["nodes"]}

N_SHOTS = 20
COLS = 4
ROWS = (N_SHOTS + COLS - 1) // COLS  # 5
COL_X = [40, 380, 720, 1060]
ROW_Y_BASE = [1800, 4400, 7000, 9600, 12200]

# per-shot node template ids (from the 4-shot attachment)
T = {
    "obj":       106,   # GetObjectFromJson
    "img":       107,   # GetTextFromJson image_prompt
    "vid":       108,   # GetTextFromJson video_prompt
    "dlg":       109,   # GetTextFromJson dialogue
    "dur":       228,   # GetTextFromJson duration
    "dur_regex": 216,   # RegexExtract duration number
    "dur_conv":  218,   # easy convertAnything -> float
    "msa":       125,   # ModelSamplingAuraFlow
    "enc":       126,   # CLIPTextEncode
    "neg":       127,   # ConditioningZeroOut
    "lat":       128,   # EmptySD3LatentImage
    "ks":        129,   # KSampler
    "vdec_img":  130,   # VAEDecode (image)
    "join":      158,   # JoinStrings
    "frames":    157,   # ComfyMathExpression
    "i2v":       254,   # MiniMaxH3ImageToVideo
    "guider":    160,   # BasicGuider
    "sched":     161,   # BasicScheduler
    "noise":     162,   # RandomNoise
    "ksel":      163,   # KSamplerSelect
    "sca":       164,   # SamplerCustomAdvanced
    "vdec_vid":  165,   # VAEDecode (video)
    "adec":      166,   # VAEDecodeAudio
    "create":    167,   # CreateVideo
    "save":      168,   # SaveVideo
}

ORDER = ["obj", "img", "vid", "dlg", "dur", "dur_regex", "dur_conv",
         "msa", "enc", "neg", "lat", "ks", "vdec_img",
         "join", "frames", "i2v",
         "guider", "sched", "noise", "ksel", "sca", "vdec_vid", "adec", "create", "save"]

TITLES = {
    "obj": "镜头{} 对象", "img": "镜头{} 画面提示词", "vid": "镜头{} 视频提示词",
    "dlg": "镜头{} 对白", "dur": "镜头{} 时长文本", "dur_regex": "镜头{} 时长提取",
    "dur_conv": "镜头{} 时长转浮点", "msa": "镜头{} AuraFlow", "enc": "镜头{} 正提示",
    "neg": "镜头{} 负提示", "lat": "镜头{} 潜空间", "ks": "镜头{} Z-Image采样",
    "vdec_img": "镜头{} 解码", "join": "镜头{} H3提示词", "frames": "镜头{} 帧数",
    "i2v": "镜头{} 图生视频", "guider": "镜头{} 引导", "sched": "镜头{} 调度",
    "noise": "镜头{} 噪声", "ksel": "镜头{} 采样器", "sca": "镜头{} 高级采样",
    "vdec_vid": "镜头{} 视频解码", "adec": "镜头{} 音频解码",
    "create": "镜头{} 合成视频", "save": "镜头{} 保存片段",
}

# y offset within a shot column (relative to row y_base)
Y_OFF = {
    "obj": 0, "img": 110, "vid": 210, "dlg": 310, "dur": 410,
    "dur_regex": 510, "dur_conv": 610,
    "msa": 720, "enc": 820, "neg": 920, "lat": 1020, "ks": 1120, "vdec_img": 1220,
    "join": 1320, "frames": 1420, "i2v": 1520,
    "guider": 1800, "sched": 1880, "noise": 1960, "ksel": 2040,
    "sca": 2120, "vdec_vid": 2200, "adec": 2280, "create": 2360, "save": 2440,
}

SHARED_IDS = [100, 101, 102, 103, 104, 105,
              122, 123, 124, 149, 150, 151, 152, 153, 154, 155, 232]
MERGE_TID = 211
FINAL_TID = 214

def clear_links(n):
    n = copy.deepcopy(n)
    for inp in n.get("inputs", []):
        inp["link"] = None
    for out in n.get("outputs", []):
        out["links"] = []
    return n

# ---------- build nodes ----------
new_nodes = []
node_of = {}

# shared nodes (keep original ids)
for nid in SHARED_IDS:
    n = clear_links(src[nid])
    new_nodes.append(n)
    node_of[nid] = n

# relocate shared models
set_pos = lambda nid, x, y: node_of[nid].update({"pos": [x, y]})
set_pos(122, 40, 1300)     # Z-Image CLIP
set_pos(123, 360, 1300)    # Z-Image UNET
set_pos(124, 680, 1300)    # Z-Image VAE
set_pos(149, 40, 1500)     # H3 CLIP
set_pos(150, 360, 1500)    # H3 video VAE
set_pos(151, 680, 1500)    # H3 audio VAE
set_pos(152, 1000, 1500)   # H3 UNET
set_pos(153, 1340, 1500)   # SageAttention
set_pos(154, 1680, 1500)   # TESpeed
set_pos(155, 1980, 1300)   # ResolutionSelector (shared)

# fix system_prompt: 4 -> 20 shots
wv = node_of[103]["widgets_values"]
sp = wv[2]
sp = sp.replace("共 4 个镜头（shot 1-4）", "共 20 个镜头（shot 1-20）")
wv[2] = sp

# per-shot nodes
for i in range(N_SHOTS):
    base = 300 + i * 25
    col = i % COLS
    row = i // COLS
    x = COL_X[col]
    yb = ROW_Y_BASE[row]
    for k, key in enumerate(ORDER):
        nid = base + k
        n = clear_links(src[T[key]])
        n["id"] = nid
        n["title"] = TITLES[key].format(i + 1)
        n["pos"] = [x, yb + Y_OFF[key]]
        n["order"] = len(new_nodes)
        n["mode"] = 0
        # adjust widgets_values
        wvv = n.get("widgets_values", [])
        if key == "obj":
            wvv[0] = f"shots.[{i}]"
        elif key == "ks":
            wvv[0] = 555659970080719 + i * 1000
        elif key == "noise":
            wvv[0] = 709710297400660 + i * 1000
        elif key == "save":
            wvv[0] = f"drama_shot_{i + 1}"
        elif key == "i2v":
            wvv[0] = ""  # prompt placeholder (linked)
        new_nodes.append(n)
        node_of[nid] = n

# merge chain: 19 merge nodes + 1 final save
merge_ids = []
for i in range(N_SHOTS - 1):
    nid = 800 + i
    n = clear_links(src[MERGE_TID])
    n["id"] = nid
    n["title"] = f"⑥ 合并镜头1-{i + 2}"
    n["pos"] = [40, 15000 + i * 120]
    n["order"] = len(new_nodes)
    new_nodes.append(n)
    node_of[nid] = n
    merge_ids.append(nid)

final_id = 820
n = clear_links(src[FINAL_TID])
n["id"] = final_id
n["pos"] = [380, 15000 + (N_SHOTS - 1) * 120]
n["order"] = len(new_nodes)
new_nodes.append(n)
node_of[final_id] = n

# ---------- build links ----------
links = []
_next = [6000]

def add_link(src_id, src_slot, dst_id, dst_slot, typ):
    lid = _next[0]
    _next[0] += 1
    links.append([lid, src_id, src_slot, dst_id, dst_slot, typ])
    # dst input link
    dst = node_of[dst_id]
    ins = dst.get("inputs", [])
    if isinstance(dst_slot, int) and 0 <= dst_slot < len(ins):
        ins[dst_slot]["link"] = lid
    # src output links
    src = node_of[src_id]
    outs = src.get("outputs", [])
    if isinstance(src_slot, int) and 0 <= src_slot < len(outs):
        if outs[src_slot].get("links") is None:
            outs[src_slot]["links"] = []
        outs[src_slot]["links"].append(lid)
    return lid

# shared chain
add_link(100, 0, 103, 5, "STRING")       # story -> custom_prompt (slot 5)
add_link(101, 0, 103, 0, "LLAMACPPMODEL")
add_link(102, 0, 103, 1, "LLAMACPPARAMS")
add_link(103, 0, 104, 0, "STRING")       # preview
add_link(103, 0, 232, 0, "STRING")       # json clean
add_link(232, 0, 105, 0, "STRING")       # -> LoadJsonFromText
add_link(152, 0, 153, 0, "MODEL")        # H3 UNET -> Sage
add_link(153, 0, 154, 0, "MODEL")        # Sage -> TESpeed

# per-shot wiring
for i in range(N_SHOTS):
    base = 300 + i * 25
    obj, img, vid, dlg, dur = base, base+1, base+2, base+3, base+4
    dur_regex, dur_conv = base+5, base+6
    msa, enc, neg, lat, ks, vdec_img = base+7, base+8, base+9, base+10, base+11, base+12
    join, frames, i2v = base+13, base+14, base+15
    guider, sched, noise, ksel, sca = base+16, base+17, base+18, base+19, base+20
    vdec_vid, adec, create, save = base+21, base+22, base+23, base+24

    # script distribution
    add_link(105, 0, obj, 0, "JSON")
    add_link(obj, 0, img, 0, "JSON")
    add_link(obj, 0, vid, 0, "JSON")
    add_link(obj, 0, dlg, 0, "JSON")
    add_link(obj, 0, dur, 0, "JSON")

    # duration extraction
    add_link(dur, 0, dur_regex, 0, "STRING")
    add_link(dur_regex, 0, dur_conv, 0, "STRING")
    add_link(dur_conv, 0, frames, 0, "FLOAT")

    # Z-Image
    add_link(img, 0, enc, 1, "STRING")        # image_prompt -> text (slot 1)
    add_link(vid, 0, join, 0, "STRING")       # video_prompt -> string1
    add_link(dlg, 0, join, 1, "STRING")       # dialogue -> string2
    add_link(123, 0, msa, 0, "MODEL")         # zunet -> msa
    add_link(msa, 0, ks, 0, "MODEL")
    add_link(122, 0, enc, 0, "CLIP")          # zclip -> enc
    add_link(enc, 0, ks, 1, "CONDITIONING")
    add_link(enc, 0, neg, 0, "CONDITIONING")
    add_link(neg, 0, ks, 2, "CONDITIONING")
    add_link(lat, 0, ks, 3, "LATENT")
    add_link(ks, 0, vdec_img, 0, "LATENT")
    add_link(124, 0, vdec_img, 1, "VAE")

    # H3 image-to-video
    add_link(join, 0, i2v, 4, "STRING")       # prompt
    add_link(vdec_img, 0, i2v, 2, "IMAGE")    # first_frame
    add_link(149, 0, i2v, 0, "CLIP")
    add_link(150, 0, i2v, 1, "VAE")
    add_link(155, 0, i2v, 5, "INT")           # width
    add_link(155, 1, i2v, 6, "INT")           # height
    add_link(frames, 1, i2v, 7, "INT")        # length (INT output)

    # sampling
    add_link(154, 0, guider, 0, "MODEL")
    add_link(i2v, 0, guider, 1, "CONDITIONING")
    add_link(154, 0, sched, 0, "MODEL")
    add_link(guider, 0, sca, 1, "GUIDER")
    add_link(sched, 0, sca, 3, "SIGMAS")
    add_link(noise, 0, sca, 0, "NOISE")
    add_link(ksel, 0, sca, 2, "SAMPLER")
    add_link(i2v, 1, sca, 4, "LATENT")

    # decode video + audio
    add_link(sca, 0, vdec_vid, 0, "LATENT")
    add_link(sca, 0, adec, 0, "LATENT")
    add_link(150, 0, vdec_vid, 1, "VAE")
    add_link(151, 0, adec, 1, "VAE")

    # compose + save
    add_link(vdec_vid, 0, create, 0, "IMAGE")
    add_link(adec, 0, create, 1, "AUDIO")
    add_link(create, 0, save, 0, "VIDEO")

    # feed merge chain
    if i == 0:
        add_link(create, 0, merge_ids[0], 0, "VIDEO")
    elif i == 1:
        add_link(create, 0, merge_ids[0], 1, "VIDEO")
    else:
        # merge_ids[i-1] gets create[i] as video_2
        add_link(create, 0, merge_ids[i - 1], 1, "VIDEO")

# chain merge: merge[k] -> merge[k+1] video_1
for k in range(N_SHOTS - 2):
    add_link(merge_ids[k], 0, merge_ids[k + 1], 0, "VIDEO")

# final save
add_link(merge_ids[-1], 0, final_id, 0, "VIDEO")

# ---------- assemble workflow ----------
wf["nodes"] = new_nodes
wf["links"] = links
wf["last_node_id"] = max(n["id"] for n in new_nodes)
wf["last_link_id"] = max(l[0] for l in links)
wf["groups"] = [
    {"id": 1, "title": "① 一句话输入", "bounding": [20, 20, 400, 180], "color": "#333", "flags": {}},
    {"id": 2, "title": "② LLM 剧本导演", "bounding": [20, 280, 1050, 500], "color": "#3f2d20", "flags": {}},
    {"id": 3, "title": "共享模型 (Z-Image + H3 + 分辨率)", "bounding": [20, 1280, 2200, 420], "color": "#1f3a2d", "flags": {}},
    {"id": 4, "title": "③④⑤ 20镜头流水线 (4列×5行)", "bounding": [20, 1780, 1400, 13000], "color": "#2d1f3a", "flags": {}},
    {"id": 5, "title": "⑥ 拼接输出完整短剧", "bounding": [20, 14950, 620, 2600], "color": "#2d3a1f", "flags": {}},
]
wf["config"] = {}
wf["extra"] = {"ds": {"scale": 0.5, "offset": [0, 0]}}
wf["version"] = 0.4

with open(DST, "w", encoding="utf-8") as f:
    json.dump(wf, f, ensure_ascii=False, indent=1)

print(f"generated {len(new_nodes)} nodes, {len(links)} links -> {DST}")
print(f"shots: {N_SHOTS}, merge nodes: {len(merge_ids)}")
