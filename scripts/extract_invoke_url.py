# -*- coding: utf-8 -*-
import sys, re, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
req = urllib.request.Request("https://build.nvidia.com/wan-ai/wan2.2-animate-2-14b",
                             headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "replace")

# 找所有 invoke_url= 赋值
for m in re.finditer(r'invoke_url\s*=\s*["\']([^"\']+)["\']', html):
    print("invoke_url =", m.group(1))
# 也找 nvidiaApiUrl / apiUrl 模板
for key in ['nvidiaApiUrl', 'apiCatalogUrl', 'build.nvidia.com/api', 'modelApiUrl', 'ipText']:
    for m in re.finditer(re.escape(key) + r'[^",\s]{0,160}', html):
        v = m.group(0)
        if 'nvidia' in v or '/v1/' in v or '.com' in v:
            print(key, "->", v[:160])
