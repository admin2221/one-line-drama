# -*- coding: utf-8 -*-
import sys, json, urllib.request, urllib.error
sys.stdout.reconfigure(encoding="utf-8")
KEY = "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"

def probe(path, host="https://integrate.api.nvidia.com", method="POST", payload=None):
    url = host + path
    headers = {"Authorization": "Bearer " + KEY, "Content-Type": "application/json", "Accept": "application/json"}
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, r.read().decode("utf-8", "replace")[:300]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:300]
    except Exception as e:
        return 0, str(e)[:150]

p = {"prompt": "test", "image": "https://example.com/a.png"}
for path, pl in [
    ("/v1/videos/generations", p),
    ("/v1/video/generations", p),
    ("/v1/images:generate", p),
    ("/v1/videos:generate", p),
    ("/v1/wan-ai/wan2.2-animate-2-14b", p),
    ("/v1/genai/wan-ai/wan2.2-animate-2-14b", p),
]:
    st, body = probe(path, payload=pl)
    flag = "LIVE" if st not in (404,) else ""
    print(f"{path}  {st} {flag} | {body.replace(chr(10),' ')[:120]}")
