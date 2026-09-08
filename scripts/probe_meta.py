# -*- coding: utf-8 -*-
import sys, json, re, urllib.request, urllib.error
sys.stdout.reconfigure(encoding="utf-8")
KEY = "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"

def get(url, headers=None, timeout=40):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "Mozilla/5.0", "Authorization": "Bearer "+KEY})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, str(e)[:200]

cands = [
    "https://build.nvidia.com/wan-ai/wan2.2-animate-2-14b/api",
    "https://build.nvidia.com/wan-ai/wan2.2-animate-2-14b.json",
    "https://build.nvidia.com/_next/data/catalog/wan-ai/wan2.2-animate-2-14b.json",
    "https://build.nvidia.com/api/wan-ai/wan2.2-animate-2-14b",
]
for c in cands:
    st, body = get(c)
    print(f"== {c}  {st} | {body[:250].replace(chr(10),' ')}")
