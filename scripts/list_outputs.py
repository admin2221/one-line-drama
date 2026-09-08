# -*- coding: utf-8 -*-
"""列出输出目录镜头数与最终产物。"""
import glob
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
for base in [r"D:\Comfyui\comfyui-drama\output\5min_drama_v2_low",
             r"D:\Comfyui\comfyui-drama\output\5min_drama_v2"]:
    shots = glob.glob(os.path.join(base, "shots", "*.mp4"))
    final = os.path.join(base, "final_drama.mp4")
    print(f"{base}:")
    print(f"  shots: {len(shots)}")
    print(f"  final_drama.mp4: {'存在' if os.path.exists(final) else '不存在'}")
    if len(shots):
        sz = [os.path.getsize(s) for s in shots]
        print(f"  样例大小: {sz[:3]}... 最小{min(sz)} 最大{max(sz)}")
