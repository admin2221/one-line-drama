# -*- coding: utf-8 -*-
"""Reachability analysis: which nodes are actually executed?
ComfyUI executes nodes that are reachable from output/terminal nodes.
Terminal nodes: SaveVideo, PreviewImage, easy imageSave, SaveImage, ShowText, easy mergeVideos(final), PreviewAny.
"""
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
P = r"D:\Comfyui\Comfyui\user\default\workflows\一句话短剧20镜头.json"
wf = json.load(open(P, encoding="utf-8"))
nodes = wf["nodes"]
links = wf["links"]
node_of = {n["id"]: n for n in nodes}

TERMINAL = {"SaveVideo", "PreviewImage", "SaveImage", "easy imageSave", "ShowText|pysssss", "PreviewAny"}

# build graph: node -> set of downstream node ids (via output links)
out_edges = {n["id"]: set() for n in nodes}
for l in links:
    src_id = l[1]
    dst_id = l[3]
    out_edges[src_id].add(dst_id)

# reverse: node -> set of upstream nodes (via input links)
in_edges = {n["id"]: set() for n in nodes}
for l in links:
    in_edges[l[3]].add(l[1])

# start from terminal nodes, walk upstream (inputs)
reachable = set()
stack = [n["id"] for n in nodes if n["type"] in TERMINAL]
while stack:
    nid = stack.pop()
    if nid in reachable:
        continue
    reachable.add(nid)
    for up in in_edges[nid]:
        stack.append(up)

# also include nodes that are inputs (no input links) leading to terminals - already covered
unreachable = [nid for nid in node_of if nid not in reachable]
print(f"reachable (executed): {len(reachable)}")
print(f"UNREACHABLE (useless): {len(unreachable)}")
print()
for nid in sorted(unreachable):
    n = node_of[nid]
    print(f"  {nid:4d} [{n['type']}] title={n.get('title','')}")
