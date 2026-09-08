# -*- coding: utf-8 -*-
import sys, re, json, urllib.request, urllib.error
sys.stdout.reconfigure(encoding="utf-8")

def fetch(url, timeout=40):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")

html = fetch("https://build.nvidia.com/wan-ai/wan2.2-animate-2-14b")

# 1) 所有含 wan 的 URL
wan_urls = re.findall(r'https?://[a-zA-Z0-9._\-/]*wan[a-zA-Z0-9._\-/]*', html, re.I)
print("== wan URLs ==")
for u in list(dict.fromkeys(wan_urls))[:20]:
    print("  ", u)

# 2) 所有 /v1/ 路径
paths = re.findall(r'https://ai\.api\.nvidia\.com/v1/[a-zA-Z0-9_\-/]+', html)
print("\n== ai.api.nvidia.com/v1 paths ==")
for u in list(dict.fromkeys(paths)):
    print("  ", u)

# 3) 内嵌的请求样例 JSON（找 "model" 或 "invocation" 或字符串含 wan2.2）
print("\n== snippets containing wan2.2 ==")
idxs = [m.start() for m in re.finditer(r'wan2\.2', html, re.I)]
for i in idxs[:6]:
    print("   ...", html[i-40:i+160].replace("\n", " ")[:200])
