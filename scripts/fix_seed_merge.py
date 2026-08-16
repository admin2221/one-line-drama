# -*- coding: utf-8 -*-
"""Two fixes:
1) 每镜头递增 seed: 20 RandomNoise nodes -> fixed seed BASE+i (i=0..19), control='fixed'.
2) 强制 merge 串行: for shot N (3..20), route first_frame through ImpactExecutionOrderController
   whose signal = merge(797+N) (合并1..N-1) VIDEO, value = shot N-1 tail-frame IMAGE.
   This forces merge of first N-1 shots to finish before shot N's H3 starts.
"""
import json, shutil, sys, datetime
sys.stdout.reconfigure(encoding="utf-8")

P = r"D:\Comfyui\Comfyui\user\default\workflows\一句话短剧20镜头.json"
BAK = P + ".bak_seed_merge_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
shutil.copy2(P, BAK)
print("backup ->", BAK)

wf = json.load(open(P, encoding="utf-8"))
nodes = wf["nodes"]
links = wf["links"]
node_by_id = {n["id"]: n for n in nodes}
link_by_id = {l[0]: l for l in links}

# ============ 1. 每镜头递增 seed ============
BASE_SEED = 1108647597087999
for shot in range(1, 21):
    rn_id = 318 + (shot - 1) * 25
    n = node_by_id.get(rn_id)
    if n is None:
        print(f"  WARN: RandomNoise {rn_id} missing")
        continue
    n["widgets_values"] = [BASE_SEED + (shot - 1), "fixed"]
print("seed done: RandomNoise -> fixed, BASE+i")

# ============ 2. 强制 merge 串行 ============
next_node_id = max(n["id"] for n in nodes) + 1
next_link_id = max(l[0] for l in links) + 1

for shot in range(3, 21):  # shots 3..20
    # shot N ids
    i2v_id = 315 + (shot - 1) * 25          # shot N i2v
    tail_id = 915 + (shot - 2) * 6          # shot N-1 tail GetVideoComponents
    merge_id = 797 + shot                   # merge of shots 1..(N-1): 800..817

    i2v = node_by_id.get(i2v_id)
    tail = node_by_id.get(tail_id)
    merge = node_by_id.get(merge_id)
    if i2v is None or tail is None or merge is None:
        print(f"  WARN: shot{shot} i2v={i2v_id} tail={tail_id} merge={merge_id} missing")
        continue

    # find first_frame input slot + its current link (tail -> i2v)
    ff_slot = None
    ff_link = None
    for idx, i in enumerate(i2v.get("inputs", [])):
        if i["name"] == "first_frame":
            ff_slot = idx
            if i.get("link"):
                ff_link = link_by_id.get(i["link"])
            break
    if ff_slot is None or ff_link is None:
        print(f"  WARN: shot{shot} first_frame link not found")
        continue

    ff_link_id = ff_link[0]

    # create order controller node
    ctrl_id = next_node_id
    next_node_id += 1
    ctrl = {
        "id": ctrl_id,
        "type": "ImpactExecutionOrderController",
        "pos": [1800, 200 + shot * 40],
        "size": [210, 58],
        "flags": {},
        "order": 0,
        "mode": 0,
        "inputs": [
            {"name": "signal", "type": "*", "link": None},
            {"name": "value", "type": "*", "link": None},
        ],
        "outputs": [
            {"name": "signal", "type": "*", "links": [], "slot_index": 0},
            {"name": "value", "type": "*", "links": [ff_link_id], "slot_index": 1},
        ],
        "properties": {"Node name for S&R": "ImpactExecutionOrderController"},
        "widgets_values": [],
    }
    nodes.append(ctrl)
    node_by_id[ctrl_id] = ctrl

    # new links: merge -> signal, tail -> value
    signal_link_id = next_link_id
    next_link_id += 1
    value_link_id = next_link_id
    next_link_id += 1

    links.append([signal_link_id, merge_id, 0, ctrl_id, 0, "VIDEO"])
    links.append([value_link_id, tail_id, 0, ctrl_id, 1, "IMAGE"])

    ctrl["inputs"][0]["link"] = signal_link_id
    ctrl["inputs"][1]["link"] = value_link_id

    # rewire first_frame link: src tail -> ctrl value output (slot 1)
    ff_link[1] = ctrl_id
    ff_link[2] = 1
    ff_link[5] = "IMAGE"

    # update tail node outputs: remove ff_link_id, add value_link_id
    tail_out = tail["outputs"][0]
    tail_out["links"] = [x for x in tail_out.get("links", []) if x != ff_link_id]
    tail_out["links"].append(value_link_id)

    # update merge node outputs: add signal_link_id
    merge["outputs"][0].setdefault("links", [])
    if signal_link_id not in merge["outputs"][0]["links"]:
        merge["outputs"][0]["links"].append(signal_link_id)

print(f"merge-serial done: added {21-3} controllers, next_node_id={next_node_id}, next_link_id={next_link_id}")

# renumber order
nodes.sort(key=lambda n: n["id"])
for idx, n in enumerate(nodes):
    n["order"] = idx

wf["nodes"] = nodes
wf["links"] = links
wf["last_node_id"] = max(n["id"] for n in nodes)
wf["last_link_id"] = max(l[0] for l in links)
wf["version"] = 0.4

json.dump(wf, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"saved. nodes={len(nodes)}, links={len(links)}")
