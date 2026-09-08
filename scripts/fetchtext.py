# -*- coding: utf-8 -*-
"""打印指定 prompt 的第一个文本输出。"""
import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
pid = sys.argv[1]
with urllib.request.urlopen(f"http://127.0.0.1:8188/history/{pid}", timeout=10) as r:
    h = json.loads(r.read().decode())
entry = h.get(pid, {})
for nid, outs in entry.get("outputs", {}).items():
    for k in ("text", "string"):
        if k in outs:
            v = outs[k]
            print("".join(v) if isinstance(v, list) else str(v))
            sys.exit(0)
print("(无文本输出)")
