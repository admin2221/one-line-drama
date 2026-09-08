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
        return 0, str(e)

# 1) with key, list all models on integrate host
for host in ["https://integrate.api.nvidia.com", "https://ai.api.nvidia.com"]:
    st, body = get(host + "/v1/models", headers={"Authorization": "Bearer " + KEY})
    print(f"== {host}/v1/models  HTTP {st}")
    try:
        d = json.loads(body)
        ms = d.get("data", [])
        wan = [m["id"] for m in ms if "wan" in m.get("id", "").lower()]
        print("   wan models:", wan)
        print("   total:", len(ms))
    except Exception:
        print("   raw:", body[:300])
    print()
