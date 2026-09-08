# -*- coding: utf-8 -*-
"""查询 ComfyUI 队列与最近 history 状态。"""
import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")


def get(path):
    with urllib.request.urlopen("http://127.0.0.1:8188" + path, timeout=10) as r:
        return json.loads(r.read().decode())


q = get("/queue")
print("running:", len(q.get("queue_running", [])), "pending:", len(q.get("queue_pending", [])))
for it in q.get("queue_running", []):
    print("  running prompt:", it[0], it[1][:40])

h = get("/history")
print("history count:", len(h))
for pid, entry in list(h.items())[-2:]:
    st = entry.get("status", {})
    print(f"  {pid[:16]} status={st.get('status_str')} outputs={list(entry.get('outputs', {}).keys())}")
