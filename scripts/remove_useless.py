# -*- coding: utf-8 -*-
"""Remove useless nodes from the workflow:
  - Shots 2-20 Z-Image generation chain (GetTextFromJson image_prompt,
    ModelSamplingAuraFlow, CLIPTextEncode, ConditioningZeroOut, EmptySD3LatentImage,
    KSampler, VAEDecode) - orphaned after last-frame chaining took over first_frame.
  - Keep tool nodes (easy clearCacheAll, LayerUtility TextBox, easy cleanGpuUsed) for now.
"""
import json, shutil, sys, datetime
sys.stdout.reconfigure(encoding="utf-8")

P = r"D:\Comfyui\Comfyui\user\default\workflows\一句话短剧20镜头.json"
BAK = P + ".bak_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
shutil.copy2(P, BAK)
print("backup ->", BAK)

wf = json.load(open(P, encoding="utf-8"))
nodes = wf["nodes"]
L = wf["links"]

# ---- identify nodes to remove ----
# per shot (index i in 1..19 => shot i+2), base = 300 + shot*25
to_remove = set()
for shot in range(2, 21):  # shots 2..20
    base = 300 + (shot - 1) * 25
    # shot node ids:
    # img = base+1 (GetTextFromJson image_prompt)
    # msa = base+7, enc = base+8, neg = base+9, lat = base+10, ks = base+11, vdec = base+12
    for off in (1, 7, 8, 9, 10, 11, 12):
        to_remove.add(base + off)

print(f"removing {len(to_remove)} nodes:", sorted(to_remove))

# ---- collect links touching these nodes ----
touched = set()
for n in nodes:
    if n["id"] in to_remove:
        for i in n.get("inputs", []):
            if i.get("link") is not None:
                touched.add(i["link"])
        for o in n.get("outputs", []):
            for l in (o.get("links") or []):
                touched.add(l)
print(f"removing {len(touched)} links")

# ---- filter ----
new_nodes = [n for n in nodes if n["id"] not in to_remove]
new_links = [l for l in L if l[0] not in touched]

# clean dangling refs
for n in new_nodes:
    for i in n.get("inputs", []):
        if i.get("link") in touched:
            i["link"] = None
    for o in n.get("outputs", []):
        if o.get("links"):
            o["links"] = [x for x in o["links"] if x not in touched]

# renumber order
new_nodes.sort(key=lambda n: n["id"])
for idx, n in enumerate(new_nodes):
    n["order"] = idx

wf["nodes"] = new_nodes
wf["links"] = new_links
wf["last_node_id"] = max(n["id"] for n in new_nodes)
wf["last_link_id"] = max(l[0] for l in new_links)
wf["version"] = 0.4

with open(P, "w", encoding="utf-8") as f:
    json.dump(wf, f, ensure_ascii=False, indent=1)

print(f"saved. nodes: {len(new_nodes)} (was {len(nodes)}), links: {len(new_links)} (was {len(L)})")
