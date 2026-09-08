# -*- coding: utf-8 -*-
import sys, json, urllib.request, urllib.error
sys.stdout.reconfigure(encoding="utf-8")

KEY = "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"

def probe(path, host="https://ai.api.nvidia.com", method="POST", payload=None):
    url = host + path
    headers = {"Authorization": "Bearer " + KEY, "Content-Type": "application/json"}
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, r.read().decode("utf-8", "replace")[:500]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:500]
    except Exception as e:
        return 0, str(e)[:250]

# 探测候选视频 orchestrator 路径
candidates = [
    "/v1/video/wan-ai/wan2.2-animate-2-14b",
    "/v1/genai/wan-ai/wan2.2-animate-2-14b",
    "/v1/video/wan2.2-animate/wan2.2-animate-2-14b",
    "/v1/video/wan_ai/wan2.2-animate-2-14b",
]
payload = {"image": None, "prompt": "test", "response_format": "b64_json"}
for c in candidates:
    st, body = probe(c, payload=payload)
    print(f"--- {c}\n    HTTP {st} | {body.replace(chr(10),' ')[:250]}")
