# -*- coding: utf-8 -*-
"""列出 drama_workplace_3min 完整产物并检查参考图。"""
import glob
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
base = r"D:\Comfyui\comfyui-drama\output\drama_workplace_3min"
print("=== drama_workplace_3min (3分钟都市职场) ===")
p = os.path.join(base, "final_drama.mp4")
print(f"  final_drama.mp4: {os.path.getsize(p)} bytes" if os.path.exists(p) else "  final_drama.mp4: 缺失")
p = os.path.join(base, "script.json")
print(f"  script.json: {os.path.getsize(p)} bytes" if os.path.exists(p) else "  script.json: 缺失")
print("  参考图:")
for f in sorted(glob.glob(os.path.join(base, "*.png"))):
    print(f"    {os.path.basename(f)}: {os.path.getsize(f)} bytes")
shots = glob.glob(os.path.join(base, "shots", "*.mp4"))
print(f"  shots: {len(shots)} 个镜头")
