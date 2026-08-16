# -*- coding: utf-8 -*-
"""Submit the workflow for real execution."""
import json, sys, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
api = json.load(open(r"D:\Comfyui\Comfyui\scripts\generated_api_clean.json", encoding="utf-8"))

# confirm input sentence + resolution are in the API
n100 = api.get("100", {})
print("node100 value:", json.dumps(n100.get("inputs", {}).get("value"), ensure_ascii=False)[:200])

payload = json.dumps({"prompt": api, "client_id": "drama20-run1"}).encode("utf-8")
req = urllib.request.Request("http://127.0.0.1:8188/prompt", data=payload, headers={"Content-Type": "application/json"})
try:
    r = urllib.request.urlopen(req, timeout=60)
    resp = json.loads(r.read().decode("utf-8"))
    print("SUBMITTED prompt_id:", resp.get("prompt_id"), "number:", resp.get("number"))
    print("node_errors:", resp.get("node_errors"))
    with open(r"D:\Comfyui\Comfyui\scripts\last_prompt_id.txt", "w") as f:
        f.write(resp.get("prompt_id", ""))
except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8", errors="replace")
    print("HTTP", e.code)
    print(body[:3000])
