# -*- coding: utf-8 -*-
import sys, re, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
req = urllib.request.Request("https://build.nvidia.com/wan-ai/wan2.2-animate-2-14b",
                             headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "replace")

# 搜索包含 nvidia/ 或 /v1/ 或 genai 或 video 的所有字符串片段
for pat in [r'["\']([^"\']*nvidia\.com/[^"\']+)["\']',
            r'["\']([^"\']*/v1/[^"\']+)["\']',
            r'["\']([^"\']*genai[^"\']*)["\']',
            r'["\']([^"\']*video/[^"\']*)["\']']:
    hits = re.findall(pat, html)
    uniq = [h for h in dict.fromkeys(hits) if 'wan' in h or 'video' in h or 'genai' in h]
    if uniq:
        print("PAT", pat, "\n  ", uniq[:15])

# __NEXT_DATA__ 之类
m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
print("\nhas __NEXT_DATA__:", bool(m))
