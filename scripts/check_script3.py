# -*- coding: utf-8 -*-
"""检查剧本 scenes/props/characters 结构。"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
d = json.load(open(r"D:\Comfyui\comfyui-drama\output\drama_3char_3min\script.json", encoding="utf-8"))
print("title:", d.get("title"))
print("characters:", [c.get("name") for c in d.get("characters", [])])
print("scenes dict keys:", list(d.get("scenes", {}).keys()))
print("props dict keys:", list(d.get("props", {}).keys()))
shots = d.get("shots", [])
print("shots:", len(shots))
print("unique scene(field) count:", len(set(s.get("scene") for s in shots)))
print("unique scene_ref count:", len(set(s.get("scene_ref") for s in shots)))
print("sample:", [{"scene": s.get("scene"), "scene_ref": s.get("scene_ref"),
                   "refs": s.get("character_refs"), "props": s.get("props")} for s in shots[:8]])
