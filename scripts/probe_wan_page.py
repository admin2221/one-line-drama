# -*- coding: utf-8 -*-
import sys, re, json, urllib.request, urllib.error
sys.stdout.reconfigure(encoding="utf-8")

def fetch(url, timeout=40):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, str(e)

st, html = fetch("https://build.nvidia.com/wan-ai/wan2.2-animate-2-14b")
print("page HTTP", st, "len", len(html))
if st != 200:
    print(html[:300]); sys.exit()

# 找 URL / endpoint / orchestrator
for pat in [r'https://[a-z0-9.\-/]+api\.nvidia\.com[a-zA-Z0-9_\-/]*',
            r'https://[a-z0-9.\-/]*nvcf[a-zA-Z0-9_\-/]*',
            r'"url"\s*:\s*"[^"]+"']:
    m = re.findall(pat, html)
    if m:
        print("PAT", pat, "->", list(dict.fromkeys(m))[:12])
