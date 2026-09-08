# -*- coding: utf-8 -*-
import sys, re, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
req = urllib.request.Request("https://build.nvidia.com/wan-ai/wan2.2-animate-2-14b",
                             headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "replace")

# 还原常见转义
h = html.replace('\\u003c','<').replace('\\u003e','>').replace('\\u0026','&')\
      .replace('\\n','\n').replace('\\"','"').replace('\\\\','\\')

# nvcfFunctionId 及其值
for m in re.finditer(r'nvcfFunctionId[^,}\]]{0,120}', h):
    print("FID:", m.group(0)[:120])

# 所有 /genai/ 与 nvidia.com/api、invoke_url、http 端点（还原后）
for m in list(dict.fromkeys(re.findall(r'https://[a-zA-Z0-9\.\-]+\.[a-z]+/[A-Za-z0-9_\-/]{3,}', h))):
    if any(k in m for k in ('genai','api','nvcf','video','wan','publisher')):
        print("URL:", m)
