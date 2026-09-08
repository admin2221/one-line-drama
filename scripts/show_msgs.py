# -*- coding: utf-8 -*-
"""打印 history entry 里所有 execution_* 消息，捕获 exception_type 等。"""
import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
pid = sys.argv[1]
with urllib.request.urlopen(f"http://127.0.0.1:8188/history/{pid}", timeout=10) as r:
    h = json.loads(r.read().decode())
entry = h.get(pid, {})
print("status_str:", entry.get("status", {}).get("status_str"))
for m in entry.get("status", {}).get("messages", []):
    kind = m[0]
    print("MSG:", kind)
    print(json.dumps(m[1], ensure_ascii=False)[:800])
