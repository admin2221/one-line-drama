# -*- coding: utf-8 -*-
"""Remove orphaned tool chain: TextBox(826) -> clearCacheAll(825) -> cleanGpuUsed(827).
The chain has no connection to the main flow (unreachable) and TextBox is empty.
"""
import json, shutil, sys, datetime
sys.stdout.reconfigure(encoding="utf-8")
P = r"D:\Comfyui\Comfyui\user\default\workflows\一句话短剧20镜头.json"
BAK = P + ".bak2_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
shutil.copy2(P, BAK)
print("backup ->", BAK)

wf = json.load(open(P, encoding="utf-8"))
nodes = wf["nodes"]
L = wf["links"]
to_remove = {825, 826, 827}
touched = set()
for n in nodes:
    if n["id"] in to_remove:
        for i in n.get("inputs", []):
            if i.get("link") is not None:
                touched.add(i["link"])
        for o in n.get("outputs", []):
            for l in (o.get("links") or []):
                touched.add(l)

new_nodes = [n for n in nodes if n["id"] not in to_remove]
new_links = [l for l in L if l[0] not in touched]
for n in new_nodes:
    for i in n.get("inputs", []):
        if i.get("link") in touched:
            i["link"] = None
    for o in n.get("outputs", []):
        if o.get("links"):
            o["links"] = [x for x in o["links"] if x not in touched]

new_nodes.sort(key=lambda n: n["id"])
for idx, n in enumerate(new_nodes):
    n["order"] = idx
wf["nodes"] = new_nodes
wf["links"] = new_links
wf["last_node_id"] = max(n["id"] for n in new_nodes)
wf["last_link_id"] = max(l[0] for l in new_links)
wf["version"] = 0.4
json.dump(wf, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"saved. nodes: {len(new_nodes)} (was {len(nodes)}), links: {len(new_links)} (was {len(L)})")
