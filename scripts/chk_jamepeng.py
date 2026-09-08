# -*- coding: utf-8 -*-
"""查询 JamePeng/llama-cpp-python 最新 release 与可用的 Windows cp312 CUDA wheel。"""
import sys
import json
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")

try:
    data = json.loads(get("https://api.github.com/repos/JamePeng/llama-cpp-python/releases?per_page=10"))
    for rel in data:
        tag = rel.get("tag_name")
        name = rel.get("name") or ""
        date = rel.get("published_at", "")[:10]
        assets = [a["name"] for a in rel.get("assets", [])]
        print(f"== {tag} ({date}) {name[:60]}")
        for a in assets:
            if "win" in a.lower() and "cp312" in a.lower():
                print("   ", a)
except Exception as e:
    print(f"❌ {type(e).__name__}: {e}")
