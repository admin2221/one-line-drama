# -*- coding: utf-8 -*-
import sys, re, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
req = urllib.request.Request("https://build.nvidia.com/wan-ai/wan2.2-animate-2-14b",
                             headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "replace")

# 找 API 相关字段
for key in ["apiUrl", "apiBase", "modelApi", "apiComposition", "nvidiaApiUrl",
            "invokeUrl", "orchestrator", "apiReference", "modelPath", "apiEndpoint",
            "assetUrl", "endpoint"]:
    for m in re.finditer(re.escape(key) + r'[^,}\]]{0,120}', html):
        s = m.group(0)
        if 'nvidia' in s.lower() or 'vc/' in s or '/v1/' in s or 'generate' in s:
            print(key, "->", s[:140])
