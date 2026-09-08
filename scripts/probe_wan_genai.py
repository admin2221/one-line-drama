# -*- coding: utf-8 -*-
import sys, json, urllib.request, urllib.error
sys.stdout.reconfigure(encoding="utf-8")
KEY = "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"

def probe(path, host="https://ai.api.nvidia.com", method="POST", payload=None):
    url = host + path
    headers = {"Authorization": "Bearer " + KEY, "Content-Type": "application/json", "Accept": "application/json"}
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, r.read().decode("utf-8", "replace")[:250]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:250]
    except Exception as e:
        return 0, str(e)[:150]

# 组合探针：非404即端点存活
models = [
    "wan-ai/wan2.2-animate-2-14b",
    "wan-ai/wan-animate-2-14b",
    "wan-ai/wan2.2-animate",
    "wan-ai/wan2.2-animate-2",
    "nvidia/wan2.2-animate-2-14b",
    "wan-ai/wan2.2_animate_2_14b",
    "wan2-2-animate-2-14-b/wan2.2-animate-2-14b",
]
p = {"prompt": "test"}
for m in models:
    st, body = probe("/v1/genai/" + m, payload=p)
    flag = "LIVE" if st != 404 else ""
    print(f"{m}  HTTP {st} {flag} | {body.replace(chr(10),' ')[:120]}")
