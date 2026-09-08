# -*- coding: utf-8 -*-
"""检查 pigking output 目录当前状态。"""
import glob
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
base = r"D:\Comfyui\comfyui-drama\output\drama_pigking_waste"
if os.path.isfile(os.path.join(base, "script.json")):
    d = json.load(open(os.path.join(base, "script.json"), encoding="utf-8"))
    print("script.json 存在")
    print("  title:", d.get("title"))
    print("  chars:", len(d.get("characters", [])), "scenes:", len(d.get("scenes", {})), "props:", len(d.get("props", {})))
    print("  shots:", len(d.get("shots", [])))
else:
    print("script.json 缺失（会被重新生成）")
shots = glob.glob(os.path.join(base, "shots", "shot_*.mp4"))
print("已生成镜头:", len(shots))
final = os.path.join(base, "final_drama.mp4")
print("final_drama 存在:", os.path.isfile(final))
# 列出最后几个镜头
import re
nums = sorted(int(os.path.splitext(os.path.basename(p))[0].split("_")[1]) for p in shots)
print("镜头号范围:", nums[:3], "...", nums[-3:] if len(nums) > 3 else nums)
