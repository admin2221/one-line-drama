# -*- coding: utf-8 -*-
"""验证 script.json 结构。"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
d = json.load(open(r"D:\Comfyui\comfyui-drama\output\5min_drama_v2\script.json", encoding="utf-8"))
print("title:", d.get("title"))
print("shots:", len(d.get("shots", [])))
print("total sec:", sum(int(str(s.get("duration", "4")).strip() or 4) for s in d.get("shots", [])))
print("shot1 keys:", list(d.get("shots", [{}])[0].keys()))
print("character:", d.get("character", "")[:60])
