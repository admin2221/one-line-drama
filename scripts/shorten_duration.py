# -*- coding: utf-8 -*-
"""把 script.json 的 duration 从 4 改为 3（缩短单镜头，降低总计算量）。"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
path = r"D:\Comfyui\comfyui-drama\output\5min_drama_v2\script.json"
d = json.load(open(path, encoding="utf-8"))
changed = 0
for s in d.get("shots", []):
    dur = str(s.get("duration", "4")).strip()
    if dur in ("4", "5"):
        s["duration"] = "3"
        changed += 1
total = sum(int(str(s.get("duration", "3")).strip() or 3) for s in d.get("shots", []))
with open(path, "w", encoding="utf-8") as f:
    json.dump(d, f, ensure_ascii=False, indent=2)
print(f"changed {changed} shots, 新总时长 {total}s")
