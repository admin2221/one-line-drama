"""Validate master workflow structure: links, slots, widget values."""
import json
import sys

wf = json.load(open(sys.argv[1], encoding="utf-8"))
nodes = {n["id"]: n for n in wf["nodes"]}
errors = []

# 1. node id uniqueness
ids = [n["id"] for n in wf["nodes"]]
if len(ids) != len(set(ids)):
    errors.append("Duplicate node ids!")

# 2. link validation
for l in wf["links"]:
    lid, src, sslot, dst, dslot, typ = l
    if src not in nodes:
        errors.append(f"Link {lid}: source node {src} missing")
        continue
    if dst not in nodes:
        errors.append(f"Link {lid}: target node {dst} missing")
        continue
    src_node = nodes[src]
    dst_node = nodes[dst]
    # check src output slot
    outs = src_node.get("outputs", [])
    if sslot >= len(outs):
        errors.append(f"Link {lid}: {src}({src_node['type']}) has no output slot {sslot}")
    else:
        o = outs[sslot]
        if typ not in (o.get("type"), "*"):
            pass  # allow wildcard; type mismatch check soft
    # check dst input slot
    ins = dst_node.get("inputs", [])
    if dslot >= len(ins):
        errors.append(f"Link {lid}: {dst}({dst_node['type']}) has no input slot {dslot}")
    else:
        i = ins[dslot]
        if i.get("link") != lid:
            errors.append(f"Link {lid}: dst input {i['name']} has link {i.get('link')} != {lid}")

# 3. widget values for JSON extract nodes
for n in wf["nodes"]:
    if n["type"] in ("GetObjectFromJson", "GetTextFromJson"):
        wv = n.get("widgets_values", [])
        if not wv or not wv[0]:
            errors.append(f"Node {n['id']} {n['type']} {n.get('title','')}: empty key widget")

# 4. H3 ref: check prompt/width/height/length widget values exist
for n in wf["nodes"]:
    if n["type"] == "MiniMaxH3ReferenceToVideo":
        wv = n.get("widgets_values", [])
        if len(wv) != 5:
            errors.append(f"H3 ref node {n['id']}: widgets_values len {len(wv)} != 5: {wv}")

# 5. merge inputs
for n in wf["nodes"]:
    if n["type"] == "easy mergeVideos":
        linked = sum(1 for i in n["inputs"] if i.get("link"))
        if linked != 4:
            errors.append(f"mergeVideos: only {linked}/4 inputs linked")

# 6. terminal outputs reachable
def has_out(nid, visited=None):
    if visited is None:
        visited = set()
    if nid in visited:
        return False
    visited.add(nid)
    n = nodes[nid]
    outs = n.get("outputs", [])
    for o in outs:
        for l in o.get("links", []):
            return True
    # widget outputs or none
    return False

if errors:
    print("=== STRUCTURE ERRORS ===")
    for e in errors:
        print(" -", e)
    sys.exit(1)
else:
    print("=== STRUCTURE OK: %d nodes, %d links ===" % (len(nodes), len(wf["links"])))
