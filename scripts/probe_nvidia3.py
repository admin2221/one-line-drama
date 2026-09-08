# -*- coding: utf-8 -*-
import sys, json, urllib.request, urllib.error
sys.stdout.reconfigure(encoding="utf-8")

def try_endpoint(path, payload=None, headers=None):
    url = "https://integrate.api.nvidia.com" + path
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(url, data=data, headers=headers or {},
                                 method="POST" if payload else "GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")[:400]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:400]
    except Exception as e:
        return 0, str(e)[:200]

for path in ["/v1/video/generations",
             "/v1/images/generations",
             "/v1/chat/completions"]:
    status, body = try_endpoint(path, payload={})
    print(f"--- {path}")
    print("   HTTP", status, "|", body.replace("\n", " ")[:250])
