# -*- coding: utf-8 -*-
import sys, json, urllib.request, urllib.error
sys.stdout.reconfigure(encoding="utf-8")
KEY = "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"

def get(url, headers=None, timeout=40):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, str(e)[:150]

# Try to discover the OpenAPI spec for the wan model on integrate host
for doc in [
    "/v1/models.json",
    "/wan-ai/wan2.2-animate-2-14b/openapi.json",
    "/v1/wan-ai/wan2.2-animate-2-14b",
]:
    st, body = get("https://integrate.api.nvidia.com" + doc, headers={"Authorization": "Bearer " + KEY})
    print(f"== {doc}  HTTP {st} | {body.replace(chr(10),' ')[:200]}")
