# -*- coding: utf-8 -*-
"""检查养猪首富剧本结构。"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
d = json.load(open(r"D:\Comfyui\comfyui-drama\output\drama_pigking_waste\script.json", encoding="utf-8"))
print("title:", d.get("title"))
print("characters:", len(d.get("characters", [])), [c.get("name") for c in d.get("characters", [])])
print("scenes:", len(d.get("scenes", {})), "props:", len(d.get("props", {})))
shots = d.get("shots", [])
print("shots:", len(shots))
total = sum(int(str(s.get("duration", "5")).strip() or 5) for s in shots)
print("总时长:", total, "s (~%.1f 分钟)" % (total / 60))
durs = {}
for s in shots:
    dv = int(str(s.get("duration", "5")).strip() or 5)
    durs[dv] = durs.get(dv, 0) + 1
print("时长分布:", durs)
print("全镜头含 transition_prev:", all("transition_prev" in s for s in shots))
chars_ref = set()
for s in shots:
    chars_ref.update(s.get("character_refs", []))
print("镜头出现的角色:", chars_ref)
print("sample:", json.dumps(shots[0], ensure_ascii=False)[:250])
