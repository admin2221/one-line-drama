# -*- coding: utf-8 -*-
import sys, json, urllib.request
sys.stdout.reconfigure(encoding="utf-8")

def get(url, headers=None, timeout=40):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")

raw = get("https://integrate.api.nvidia.com/v1/models")
d = json.loads(raw)
ms = d.get("data", [])
ids = [m["id"] for m in ms]
print("all model ids (first 120):")
for i in ids[:120]:
    print("  ", i)
print("--- structure of first item ---")
if ms:
    print(json.dumps(ms[0], ensure_ascii=False)[:400])
