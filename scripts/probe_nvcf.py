# -*- coding: utf-8 -*-
import sys, json, urllib.request, urllib.error
sys.stdout.reconfigure(encoding="utf-8")
KEY = "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"

def probe(path, host, method="GET", payload=None):
    url = host + path
    headers = {"Authorization":"Bearer "+KEY,"Content-Type":"application/json","Accept":"application/json"}
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, r.read().decode("utf-8","replace")[:500]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8","replace")[:500]
    except Exception as e:
        return 0, str(e)[:200]

cands = [
    ("https://api.nvcf.nvidia.com/v2/nvcf", "/models"),
    ("https://api.nvcf.nvidia.com/v2/nvcf", "/functions?name=wan"),
    ("https://api.nvcf.nvidia.com/v2/nvcf", "/models?name=wan"),
]
for host, path in cands:
    st, body = probe(path, host)
    print(f"== {host}{path}  {st} | {body[:300].replace(chr(10),' ')}")
