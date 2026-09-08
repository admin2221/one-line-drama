# -*- coding: utf-8 -*-
import sys, json, urllib.request
sys.stdout.reconfigure(encoding="utf-8")

def get(url, headers=None, timeout=40):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")

# 1) 模型列表
try:
    raw = get("https://integrate.api.nvidia.com/v1/models")
    d = json.loads(raw)
    ms = d.get("data", [])
    wan = [m["id"] for m in ms if "wan" in m.get("id", "").lower() or "animate" in m.get("id", "").lower() or "animate" in (m.get("owned_by") or "").lower()]
    print("== wan/animate models ==")
    for w in wan[:15]:
        print("  ", w)
    print("total models:", len(ms))
except Exception as e:
    print("GET /v1/models failed:", str(e)[:300])
