# -*- coding: utf-8 -*-
import sys, json, urllib.request, urllib.error, time
sys.stdout.reconfigure(encoding="utf-8")
KEY = "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"

def chat(payload, timeout=30):
    req = urllib.request.Request(
        "https://integrate.api.nvidia.com/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"},
        method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")[:400], time.time()-t0
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:400], time.time()-t0
    except Exception as e:
        return 0, str(e)[:250], time.time()-t0

p = {"model": "meta/llama-3.3-70b-instruct",
     "messages": [{"role": "user", "content": "Say exactly: ok"}],
     "max_tokens": 100}
st, body, dt = chat(p, timeout=25)
print(f"normal: {st} in {dt:.1f}s | {body[:300]}")
