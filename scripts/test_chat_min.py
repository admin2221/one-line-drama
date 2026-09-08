# -*- coding: utf-8 -*-
import sys, json, urllib.request, urllib.error
sys.stdout.reconfigure(encoding="utf-8")
KEY = "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"

def chat(payload):
    req = urllib.request.Request(
        "https://integrate.api.nvidia.com/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode("utf-8", "replace")[:500]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:500]
    except Exception as e:
        return 0, str(e)[:300]

tests = [
    ("minimal", {"model": "meta/llama-3.3-70b-instruct",
                 "messages": [{"role": "user", "content": "说\"ok\"两个字母"}]}),
    ("with max_tokens 12000", {"model": "meta/llama-3.3-70b-instruct",
                 "messages": [{"role": "user", "content": "说\"ok\"两个字母"}],
                 "max_tokens": 12000}),
    ("max_tokens 4096 + temp", {"model": "meta/llama-3.3-70b-instruct",
                 "messages": [{"role": "user", "content": "说\"ok\"两个字母"}],
                 "max_tokens": 4096, "temperature": 0.7}),
]
for name, p in tests:
    st, body = chat(p)
    print(f"== {name} -> {st} | {body[:250].replace(chr(10),' ')}")
