# -*- coding: utf-8 -*-
import sys, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8","replace")
body = get("https://docs.nvidia.com/nim/visual-genai/latest/_static/_static/yaml/wan2.2-animate.openapi.yaml")

for key in ['VideoRequest:', 'VideoResponse:', 'Artifact:', '  Health']:
    i = body.find(key)
    if i != -1:
        print(f"\n===== {key} =====")
        print(body[i:i+1400])
