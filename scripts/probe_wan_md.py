# -*- coding: utf-8 -*-
import sys, re, urllib.request, urllib.error
sys.stdout.reconfigure(encoding="utf-8")

def fetch(url, timeout=40):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")

md = fetch("https://build.nvidia.com/wan-ai/wan2.2-animate-2-14b.md")
print("md len:", len(md))
# 提取所有 URL
urls = re.findall(r'https?://[a-zA-Z0-9._\-/]+', md)
print("== URLs ==")
for u in list(dict.fromkeys(urls))[:30]:
    print("  ", u)
# 打印含 curl / invocation / api 的行
print("\n== lines with api/curl/invoke ==")
for line in md.splitlines():
    if 'api.nvidia' in line or 'curl' in line.lower() or 'invoke' in line.lower() or '/v1/' in line:
        print("  ", line.strip()[:200])
