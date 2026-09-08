# -*- coding: utf-8 -*-
import sys, urllib.request, urllib.error
sys.stdout.reconfigure(encoding="utf-8")

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8","replace")

for rel in ["_static/_static/yaml/wan2.2-animate.openapi.yaml",
            "api/_static/_static/yaml/wan2.2-animate.openapi.yaml",
            "_static/yaml/wan2.2-animate.openapi.yaml"]:
    url = "https://docs.nvidia.com/nim/visual-genai/latest/" + rel
    try:
        body = get(url)
        print(f"== {rel}  len {len(body)}")
        print(body[:3000])
        break
    except Exception as e:
        print("fail", rel, e)
