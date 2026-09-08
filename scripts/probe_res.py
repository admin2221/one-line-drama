# -*- coding: utf-8 -*-
"""Probe ResolutionSelector options + upload/download endpoints."""
import json
import urllib.request

API = "http://127.0.0.1:8188"

# ResolutionSelector options
try:
    with urllib.request.urlopen(f"{API}/object_info/ResolutionSelector", timeout=8) as r:
        n = json.loads(r.read().decode()).get("ResolutionSelector", {})
        inp = n.get("input", {})
        print("aspect_ratio options:", inp["required"]["aspect_ratio"][0])
        print("megapixels:", inp["required"]["megapixels"])
except Exception as e:
    print("ResolutionSelector ERR:", e)

# upload endpoint test
try:
    req = urllib.request.Request(API + "/upload/image", method="POST")
    with urllib.request.urlopen(req, timeout=8) as r:
        print("upload ok:", r.read()[:200])
except Exception as e:
    print("upload ERR:", e)

# system stats model dirs
try:
    with urllib.request.urlopen(f"{API}/object_info/CLIPLoader", timeout=8) as r:
        n = json.loads(r.read().decode()).get("CLIPLoader", {})
        print("\nCLIPLoader clip_name:", n["input"]["required"]["clip_name"][0])
except Exception as e:
    print("CLIPLoader ERR:", e)
