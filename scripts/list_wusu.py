# -*- coding: utf-8 -*-
"""列出 drama_wusu_3min 完整产物。"""
import glob
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
base = r"D:\Comfyui\comfyui-drama\output\drama_wusu_3min"
print("=== drama_wusu_3min (五俗历险记 7分47秒) ===")
p = os.path.join(base, "final_drama.mp4")
print(f"  final_drama.mp4: {os.path.getsize(p)} bytes" if os.path.exists(p) else "  final_drama.mp4: 缺失")
p = os.path.join(base, "script.json")
print(f"  script.json: {os.path.getsize(p)} bytes" if os.path.exists(p) else "  script.json: 缺失")
chars = glob.glob(os.path.join(base, "character_*.png"))
scenes = glob.glob(os.path.join(base, "scene_*.png"))
props = glob.glob(os.path.join(base, "prop_*.png"))
print(f"  角色定妆图: {len(chars)} 张")
print(f"  场景参考图: {len(scenes)} 张")
print(f"  物品参考图: {len(props)} 张")
shots = glob.glob(os.path.join(base, "shots", "*.mp4"))
print(f"  镜头视频: {len(shots)} 个")
