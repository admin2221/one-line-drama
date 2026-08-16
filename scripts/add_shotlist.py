# -*- coding: utf-8 -*-
"""Add a "分镜列表" (shot list) node after 105, and rewire 20 shots to consume
the list by index [0]..[19]. The tail-frame dependency chain already enforces
shot 1 -> 2 -> ... -> 20 execution order.
"""
import json, shutil, sys, datetime
sys.stdout.reconfigure(encoding="utf-8")

P = r"D:\Comfyui\Comfyui\user\default\workflows\一句话短剧20镜头.json"
BAK = P + ".bak_shotlist_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
shutil.copy2(P, BAK)
print("backup ->", BAK)

wf = json.load(open(P, encoding="utf-8"))
nodes = wf["nodes"]
links = wf["links"]

node_by_id = {n["id"]: n for n in nodes}

# shot GetObjectFromJson node ids (300 + (shot-1)*25)
shot_obj_ids = [300 + (shot - 1) * 25 for shot in range(1, 21)]

# the 20 links currently from 105 -> shot obj nodes
shot_links = []
for l in links:
    if l[1] == 105 and l[3] in shot_obj_ids:
        shot_links.append(l)
shot_links.sort(key=lambda l: l[3])  # by shot node id
assert len(shot_links) == 20, f"expected 20 shot links, got {len(shot_links)}"
shot_link_ids = [l[0] for l in shot_links]

# ---- 1. add shot-list node 106 ----
new_link_id = wf.get("last_link_id", 0) + 1  # 7133
list_node = {
    "id": 106,
    "type": "GetObjectFromJson",
    "pos": [780, 860],
    "size": [230, 100],
    "flags": {},
    "order": 0,
    "mode": 0,
    "inputs": [
        {"localized_name": "json", "name": "json", "type": "JSON", "link": new_link_id},
        {"localized_name": "key", "name": "key", "type": "STRING", "widget": {"name": "key"}, "link": None},
    ],
    "outputs": [
        {"localized_name": "JSON", "name": "JSON", "type": "JSON", "links": list(shot_link_ids)},
    ],
    "title": "②f 分镜列表",
    "properties": {"cnr_id": "comfyui-art-venture", "ver": "1.1.7", "Node name for S&R": "GetObjectFromJson"},
    "widgets_values": ["shots"],
}
nodes.append(list_node)

# ---- 2. add link 105 -> 106 ----
links.append([new_link_id, 105, 0, 106, 0, "JSON"])

# ---- 3. rewire 20 shot links: src 105 -> 106 ----
for l in shot_links:
    l[1] = 106

# ---- 4. update 105 outputs: remove 20 shot links, keep 6891 (to 823 preview), add new 7133 ----
n105 = node_by_id[105]
out_links = [x for x in n105["outputs"][0]["links"] if x not in shot_link_ids]
out_links.append(new_link_id)
n105["outputs"][0]["links"] = out_links

# ---- 5. change shot obj keys: "shots.[N]" -> "[N]" ----
for i, nid in enumerate(shot_obj_ids):
    n = node_by_id[nid]
    n["widgets_values"] = [f"[{i}]"]

# ---- 6. renumber order by id ----
nodes.sort(key=lambda n: n["id"])
for idx, n in enumerate(nodes):
    n["order"] = idx

wf["nodes"] = nodes
wf["links"] = links
wf["last_node_id"] = max(n["id"] for n in nodes)
wf["last_link_id"] = max(l[0] for l in links)
wf["version"] = 0.4

json.dump(wf, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"saved. nodes={len(nodes)}, links={len(links)}, new_link_id={new_link_id}")
print(f"shot obj keys now: {[node_by_id[n]['widgets_values'] for n in shot_obj_ids[:3]]}...")
