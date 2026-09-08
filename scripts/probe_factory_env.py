# -*- coding: utf-8 -*-
"""Check ffmpeg availability + relevant node schemas."""
import json
import shutil
import urllib.request
import subprocess

print("ffmpeg:", shutil.which("ffmpeg"))
print("ffprobe:", shutil.which("ffprobe"))
try:
    r = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=10)
    print(r.stdout.splitlines()[0] if r.stdout else "no ffmpeg")
except Exception as e:
    print("ffmpeg err:", e)

API = "http://127.0.0.1:8188"
for nt in ["easy mergeVideos", "VideoFrameSample", "GetVideoComponents",
           "easy imageSwitch", "ImpactExecutionOrderController", "JoinStrings",
           "GetTextFromJson", "GetObjectFromJson", "LoadJsonFromText",
           "RegexExtract", "easy convertAnything", "ComfyMathExpression",
           "ResolutionSelector", "easy imageSave", "easy fullkSampler"]:
    try:
        with urllib.request.urlopen(f"{API}/object_info/{nt.replace(' ', '%20')}", timeout=8) as r:
            data = json.loads(r.read().decode())
        n = data.get(nt, {})
        inp = n.get("input", {}) or {}
        out = n.get("output", []) or []
        outn = n.get("output_name", []) or []
        print(f"\n== {nt}")
        for sec in ("required", "optional"):
            for name, spec in (inp.get(sec, {}) or {}).items():
                t = spec[0] if isinstance(spec, list) else spec
                print(f"  {sec} {name}: {t}")
        print("  outputs:", list(zip(outn, out)))
    except Exception as e:
        print(f"\n== {nt} ERROR {e}")
