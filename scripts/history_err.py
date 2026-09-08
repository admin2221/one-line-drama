# -*- coding: utf-8 -*-
"""查最近任务完整 error 信息。"""
import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
pid = sys.argv[1] if len(sys.argv) > 1 else None
url = f"http://127.0.0.1:8188/history/{pid}" if pid else "http://127.0.0.1:8188/history"
with urllib.request.urlopen(url, timeout=10) as r:
    h = json.loads(r.read().decode())
target = {pid: h[pid]} if pid else h
for k, v in target.items():
    st = v.get("status", {})
    msgs = st.get("messages", [])
    print("==", k, "status:", st.get("status_str"))
    for m in msgs:
        print("  ", json.dumps(m, ensure_ascii=False)[:500])
