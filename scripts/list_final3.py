# -*- coding: utf-8 -*-
"""列出 drama_3char_3min 完整产物。"""
import glob
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
base = r"D:\Comfyui\comfyui-drama\output\drama_3char_3min"
print("=== drama_3char_3min (3分钟/3角色) ===")
for f in ["final_drama.mp4", "script.json"]:
    p = os.path.join(base, f)
    print(f"  {f}: {os.path.getsize(p)} bytes" if os.path.exists(p) else f"  {f}: 缺失")
print("  参考图:")
for f in sorted(glob.glob(os.path.join(base, "*.png"))):
    print(f"    {os.path.basename(f)}: {os.path.getsize(f)} bytes")
shots = glob.glob(os.path.join(base, "shots", "*.mp4"))
print(f"  shots: {len(shots)} 个镜头")
