# -*- coding: utf-8 -*-
import sys, re, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
req = urllib.request.Request("https://build.nvidia.com/wan-ai/wan2.2-animate-2-14b",
                             headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "replace")

# 所有 genai/ 出现
print("== all /genai/ occurrences in page ==")
for m in re.finditer(r'/genai/[A-Za-z0-9\._\-/]+', html):
    print("  ", m.group(0))
print("\n== unique genai paths ==")
for x in list(dict.fromkeys(re.findall(r'/genai/[A-Za-z0-9\._\-/]+', html))):
    print("  ", x)

# model 注册名键
print("\n== 'modelId'/'modelId'/'invokePath' fields ==")
for key in ['modelId', 'modelName', 'model-registry', 'nvcf', 'pexec', 'function', 'catalogItem']:
    for m in list(re.finditer(re.escape(key) + r'[^",<>]{0,80}', html))[:6]:
        print(key, "->", m.group(0)[:100])
