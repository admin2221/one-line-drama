# -*- coding: utf-8 -*-
"""查询指定任务详情（状态/耗时）。"""
import json
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
pid = sys.argv[1]
with urllib.request.urlopen(f"http://127.0.0.1:8188/history/{pid}", timeout=10) as r:
    h = json.loads(r.read().decode())
entry = h.get(pid, {})
st = entry.get("status", {})
print("status:", json.dumps(st, ensure_ascii=False)[:400])
