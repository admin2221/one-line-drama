# -*- coding: utf-8 -*-
import sys, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8","replace")
body = get("https://docs.nvidia.com/nim/visual-genai/latest/_static/_static/yaml/wan2.2-animate.openapi.yaml")
# 打印所有 include:/post 路径
import re
print("== paths (post/get) ==")
for m in re.finditer(r'^  (/v1/[A-Za-z0-9_\-/{}]+):$', body, re.M):
    print("  ", m.group(1))
# 打印 /infer 或 /generate 部分
for key in ['/v1/infer','/v1/generate','infer:','generate:']:
    i = body.find(key)
    if i != -1:
        print(f"\n===== section near '{key}' =====")
        print(body[i-200:i+1500])
        break
