# -*- coding: utf-8 -*-
"""Convert both source workflows to API prompt, save, and print node inventory."""
import json
import sys

sys.path.insert(0, r"D:\Comfyui\comfyui-drama\scripts")
from wf2api_full import workflow_to_api

SRC = {
    "imageai": r"D:\Comfyui\Comfyui\user\default\workflows\imageai.json",
    "h3hbai": r"D:\Comfyui\Comfyui\user\default\workflows\h3hbai.json",
}

for key, path in SRC.items():
    wf = json.load(open(path, encoding="utf-8"))
    p = workflow_to_api(wf)
    out = rf"D:\Comfyui\_factory_api_{key}.json"
    json.dump(p, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"== {key}: {len(p)} nodes -> {out}")
    for nid in sorted(p, key=int):
        ct = p[nid]["class_type"]
        ins = p[nid]["inputs"]
        wvals = {k: (str(v)[:40] if not isinstance(v, (int, float, bool)) else v) for k, v in ins.items() if not isinstance(v, list)}
        print(f"  [{nid}] {ct} {wvals}")
