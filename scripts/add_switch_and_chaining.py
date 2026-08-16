# -*- coding: utf-8 -*-
"""Add to the 20-shot workflow:
  1. Global RTX super-resolution switch (PrimitiveBoolean -> easy imageSwitch x20)
  2. Sequential generation via last-frame chaining:
     shot1 uses Z-Image reference; shot N (N>=2) uses shot N-1's video last frame
  3. First/last frame extraction per shot (VideoFrameSample + GetVideoComponents + PreviewImage)
"""
import json, copy, shutil, sys, datetime
sys.stdout.reconfigure(encoding="utf-8")

SRC = r"D:\Comfyui\.monkeycode\uploads\一句话短剧20镜头-2.json"
DST = r"D:\Comfyui\Comfyui\user\default\workflows\一句话短剧20镜头.json"

shutil.copy2(SRC, DST)
wf = json.load(open(SRC, encoding="utf-8"))
nodes = wf["nodes"]
L = wf["links"]
node_of = {n["id"]: n for n in nodes}

N_SHOTS = 20

def add_link(src_id, src_slot, dst_id, dst_slot, typ):
    new_id = max(l[0] for l in L) + 1
    L.append([new_id, src_id, src_slot, dst_id, dst_slot, typ])
    src = node_of[src_id]
    dst = node_of[dst_id]
    ins = dst.get("inputs", [])
    if isinstance(dst_slot, int) and 0 <= dst_slot < len(ins):
        ins[dst_slot]["link"] = new_id
    outs = src.get("outputs", [])
    if isinstance(src_slot, int) and 0 <= src_slot < len(outs):
        outs[src_slot].setdefault("links", []).append(new_id)
    return new_id

def remove_link(lid):
    for i in range(len(L) - 1, -1, -1):
        if L[i][0] == lid:
            del L[i]
    for n in nodes:
        for inp in n.get("inputs", []):
            if inp.get("link") == lid:
                inp["link"] = None
        for o in n.get("outputs", []):
            if o.get("links"):
                o["links"] = [x for x in o["links"] if x != lid]

def find_link(src_id, src_slot, dst_id, dst_slot):
    for l in L:
        if l[1] == src_id and l[2] == src_slot and l[3] == dst_id and l[4] == dst_slot:
            return l[0]
    return None

def mk_node(nid, ntype, pos, inputs, outputs, wv, title="", props=None):
    n = {
        "id": nid, "type": ntype, "pos": pos, "size": [230, 100],
        "flags": {}, "order": len(nodes), "mode": 0,
        "inputs": inputs, "outputs": outputs,
        "title": title,
        "properties": props or {"Node name for S&R": ntype},
        "widgets_values": wv,
    }
    nodes.append(n)
    node_of[nid] = n
    return n

# ---------- node templates ----------
def bool_input():
    return {"name": "value", "type": "BOOLEAN", "widget": {"name": "value"}, "link": None}

def switch_inputs():
    return [
        {"name": "image_a", "type": "IMAGE", "link": None},
        {"name": "image_b", "type": "IMAGE", "link": None},
        {"name": "boolean", "type": "BOOLEAN", "widget": {"name": "boolean"}, "link": None},
    ]

def vfs_inputs():
    return [
        {"name": "video", "type": "VIDEO", "link": None},
        {"name": "num_frames", "type": "INT", "widget": {"name": "num_frames"}, "link": None},
        {"name": "strategy", "type": "COMBO", "widget": {"name": "strategy"}, "link": None},
        {"name": "seed", "type": "INT", "widget": {"name": "seed"}, "link": None},
    ]

def gvc_inputs():
    return [{"name": "video", "type": "VIDEO", "link": None}]

def gvc_outputs():
    return [
        {"name": "IMAGE", "type": "IMAGE", "links": []},
        {"name": "AUDIO", "type": "AUDIO", "links": []},
        {"name": "FLOAT", "type": "FLOAT", "links": []},
        {"name": "INT", "type": "INT", "links": []},
    ]

def pv_inputs():
    return [
        {"name": "images", "type": "IMAGE", "link": None},
        {"name": "prompt", "type": "PROMPT", "link": None},
        {"name": "extra_pnginfo", "type": "EXTRA_PNGINFO", "link": None},
    ]

# ---------- 1. global RTX switch ----------
bool_id = 900
mk_node(bool_id, "PrimitiveBoolean", [40, 760], [bool_input()],
        [{"name": "BOOLEAN", "type": "BOOLEAN", "links": []}], [True], "RTX超分总开关")

switch_ids = []
for i in range(N_SHOTS):
    base = 300 + i * 25
    vdec = base + 21
    sid = 910 + i * 6
    switch_ids.append(sid)
    vp = node_of[vdec]["pos"]
    mk_node(sid, "easy imageSwitch", [vp[0] + 560, vp[1]],
            switch_inputs(),
            [{"name": "IMAGE", "type": "IMAGE", "links": []}],
            [False], f"镜头{i+1} 超分开关",
            {"cnr_id": "comfyui-easy-use", "Node name for S&R": "easy imageSwitch"})

# ---------- 2. frame extraction nodes ----------
head_ids = []   # (sample, components, preview) per shot
tail_ids = []   # (sample, components) per shot (shots 1..19)

for i in range(N_SHOTS):
    base = 300 + i * 25
    create = base + 23
    cp = node_of[create]["pos"]
    b = 910 + i * 6

    # first frame (head)
    hs = b + 1
    hc = b + 2
    hp = b + 3
    head_ids.append((hs, hc, hp))
    mk_node(hs, "VideoFrameSample", [cp[0], cp[1] + 110], vfs_inputs(),
            [{"name": "VIDEO", "type": "VIDEO", "links": []}], [1, "head", 0], f"镜头{i+1} 首帧采样")
    mk_node(hc, "GetVideoComponents", [cp[0], cp[1] + 210], gvc_inputs(),
            gvc_outputs(), [], f"镜头{i+1} 首帧提取")
    mk_node(hp, "PreviewImage", [cp[0], cp[1] + 320], pv_inputs(),
            [{"name": "IMAGE", "type": "IMAGE", "links": []}], [], f"镜头{i+1} 首帧预览")

    # last frame (tail) - not needed for the last shot
    if i < N_SHOTS - 1:
        ts = b + 4
        tc = b + 5
        tail_ids.append((ts, tc))
        mk_node(ts, "VideoFrameSample", [cp[0] + 300, cp[1] + 110], vfs_inputs(),
                [{"name": "VIDEO", "type": "VIDEO", "links": []}], [1, "tail", 0], f"镜头{i+1} 尾帧采样")
        mk_node(tc, "GetVideoComponents", [cp[0] + 300, cp[1] + 210], gvc_inputs(),
                gvc_outputs(), [], f"镜头{i+1} 尾帧提取")

# ---------- 3. rewire super-resolution switch ----------
for i in range(N_SHOTS):
    base = 300 + i * 25
    vdec = base + 21
    create = base + 23
    sid = switch_ids[i]
    # find current rtx node id for this shot
    rtx_id = None
    for l in L:
        if l[1] == vdec and l[2] == 0 and l[3] != create:
            dst = node_of.get(l[3])
            if dst and dst["type"] == "RTXVideoSuperResolution":
                rtx_id = l[3]
                break
    if rtx_id is None:
        print(f"WARN shot {i+1}: RTX node not found")
        continue
    # old link: rtx.out0 -> create.images
    old = find_link(rtx_id, 0, create, 0)
    if old:
        remove_link(old)
    # vdec -> switch.image_b (raw)
    add_link(vdec, 0, sid, 1, "IMAGE")
    # rtx -> switch.image_a (upscaled)
    add_link(rtx_id, 0, sid, 0, "IMAGE")
    # switch -> create
    add_link(sid, 0, create, 0, "IMAGE")
    # global bool -> switch.boolean (slot 2)
    add_link(bool_id, 0, sid, 2, "BOOLEAN")

# ---------- 4. first-frame chaining ----------
for i in range(N_SHOTS):
    base = 300 + i * 25
    create = base + 23
    hs, hc, hp = head_ids[i]
    # create -> head sample -> head components -> preview
    add_link(create, 0, hs, 0, "VIDEO")
    add_link(hs, 0, hc, 0, "VIDEO")
    add_link(hc, 0, hp, 0, "IMAGE")

# ---------- 5. last-frame chaining ----------
for i in range(N_SHOTS - 1):
    base = 300 + i * 25
    create = base + 23
    ts, tc = tail_ids[i]
    # current shot create -> tail sample -> tail components
    add_link(create, 0, ts, 0, "VIDEO")
    add_link(ts, 0, tc, 0, "VIDEO")
    # next shot i2v.first_frame <- tail components IMAGE
    next_base = 300 + (i + 1) * 25
    next_i2v = next_base + 15
    next_vdec_img = next_base + 12
    # remove old link next_vdec_img -> next_i2v.first_frame
    old = find_link(next_vdec_img, 0, next_i2v, 2)
    if old:
        remove_link(old)
    add_link(tc, 0, next_i2v, 2, "IMAGE")
    print(f"shot {i+2} first_frame <- shot {i+1} last frame (node {tc})")

# ---------- metadata ----------
wf["last_node_id"] = max(n["id"] for n in nodes)
wf["last_link_id"] = max(l[0] for l in L)
wf["version"] = 0.4

with open(DST, "w", encoding="utf-8") as f:
    json.dump(wf, f, ensure_ascii=False, indent=1)

print(f"\nsaved. nodes: {len(nodes)}, links: {len(L)} -> {DST}")
print(f"new nodes: 1 bool + 20 switch + 20 head(3) + 19 tail(2) = {1+20+60+38}")
