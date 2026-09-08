# -*- coding: utf-8 -*-
"""Summarize a canvas workflow: node list w/ titles, types, key widget values."""
import json
import sys
sys.stdout.reconfigure(encoding="utf-8")

wf = json.load(open(sys.argv[1], encoding="utf-8"))
nodes = wf["nodes"]
print(f"total nodes: {len(nodes)}, links: {len(wf.get('links', []))}")
for n in nodes:
    nid = n["id"]
    t = n["type"]
    title = n.get("title", "")
    wv = n.get("widgets_values", [])
    wv_str = ""
    if t in ("llama_cpp_instruct_adv",):
        wv_str = f" | sys_prompt_len={len(wv[2]) if len(wv) > 2 else 0} chars | custom={str(wv[1])[:40]}"
    elif t in ("PrimitiveStringMultiline", "PrimitiveString", "PrimitiveFloat", "CR Text"):
        wv_str = f" | val={str(wv[0])[:60]}"
    print(f"  [{nid}] {t} '{title}'{wv_str}")
