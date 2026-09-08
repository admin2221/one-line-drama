# -*- coding: utf-8 -*-
"""Find STRING-output-capable output nodes."""
import json
import urllib.request

API = "http://127.0.0.1:8188"

# list all object_info keys containing 'text' or 'save' or 'show' or 'preview'
with urllib.request.urlopen(f"{API}/object_info", timeout=15) as r:
    allinfo = json.loads(r.read().decode())

cands = [k for k in allinfo if any(s in k.lower() for s in ("text", "show", "preview", "save"))]
print("candidate nodes:")
for c in sorted(cands):
    n = allinfo[c]
    out = n.get("output", [])
    outn = n.get("output_name", [])
    is_out = n.get("output_node", False)
    if is_out or any(o == "STRING" for o in out):
        print(f"  {c} | output_node={is_out} | outputs={list(zip(outn, out))}")
