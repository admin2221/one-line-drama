# -*- coding: utf-8 -*-
"""Add RTXVideoSuperResolution to ALL 20 shots, following shot 17's layout:
  VAEDecode(video) -> RTXVideoSuperResolution -> CreateVideo
Shot 17 already has RTX (node 824); clone it for the other 19 shots.
"""
import json, copy, shutil, sys, datetime
sys.stdout.reconfigure(encoding="utf-8")

SRC = r"D:\Comfyui\.monkeycode\uploads\一句话短剧20镜头.json"
DST = r"D:\Comfyui\Comfyui\user\default\workflows\一句话短剧20镜头.json"

shutil.copy2(SRC, DST)
wf = json.load(open(SRC, encoding="utf-8"))
nodes = wf["nodes"]
L = wf["links"]
node_of = {n["id"]: n for n in nodes}

RTX_TEMPLATE = node_of[824]  # shot 17's RTX node

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

added = 0
next_rtx_id = 830

for i in range(20):
    base = 300 + i * 25
    vdec_id = base + 21      # VAEDecode (video)
    create_id = base + 23    # CreateVideo

    vdec = node_of[vdec_id]
    create = node_of[create_id]

    # find the direct link vdec.out0 -> create.images
    direct_link = None
    for l in L:
        if l[1] == vdec_id and l[2] == 0 and l[3] == create_id and l[4] == 0:
            direct_link = l[0]
            break

    if direct_link is None:
        # shot 17 already wired through RTX
        print(f"shot {i+1}: already has RTX (skip)")
        continue

    # create RTX node clone
    rtx = copy.deepcopy(RTX_TEMPLATE)
    rtx["id"] = next_rtx_id
    rtx["order"] = len(nodes)
    rtx["pos"] = [vdec["pos"][0] + 320, vdec["pos"][1] + 10]
    # clear link refs in the clone
    for inp in rtx.get("inputs", []):
        inp["link"] = None
    for o in rtx.get("outputs", []):
        o["links"] = []

    nodes.append(rtx)
    node_of[next_rtx_id] = rtx

    # rewire: vdec -> rtx -> create
    remove_link(direct_link)
    add_link(vdec_id, 0, next_rtx_id, 0, "IMAGE")
    add_link(next_rtx_id, 0, create_id, 0, "IMAGE")

    print(f"shot {i+1}: RTX node {next_rtx_id} inserted between {vdec_id} and {create_id}")
    next_rtx_id += 1
    added += 1

wf["last_node_id"] = max(n["id"] for n in nodes)
wf["last_link_id"] = max(l[0] for l in L)
wf["version"] = 0.4

with open(DST, "w", encoding="utf-8") as f:
    json.dump(wf, f, ensure_ascii=False, indent=1)

print(f"\nadded {added} RTX nodes. total nodes: {len(nodes)}, links: {len(L)} -> {DST}")
