# -*- coding: utf-8 -*-
import sys, json, urllib.request, urllib.error
sys.stdout.reconfigure(encoding="utf-8")
KEY = "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"

def probe(path, host="https://ai.api.nvidia.com", method="POST", payload=None, ctype="application/json"):
    url = host + path
    headers = {"Authorization": "Bearer " + KEY}
    if ctype: headers["Content-Type"] = ctype
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, r.read().decode("utf-8", "replace")[:400]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:400]
    except Exception as e:
        return 0, str(e)[:200]

variants = [
    "/v1/video/wan2.2_animate_2_14b",
    "/v1/genai/video/wan2.2-animate-2-14b",
    "/v1/video/wan-ai/wan2.2_animate_2_14b",
    "/v1/media/wan-ai/wan2.2-animate-2-14b",
    "/v1/video/wan_ai",
]
p = {"image": None, "prompt": "test", "response_format": "b64_json"}
for v in variants:
    st, body = probe(v, payload=p)
    print(f"--- {v}\n    {st} | {body.replace(chr(10),' ')[:200]}")
