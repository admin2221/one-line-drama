# -*- coding: utf-8 -*-
"""查看已生成镜头文件数与大小。"""
import os, sys
sys.stdout.reconfigure(encoding="utf-8")
d = r"D:\Comfyui\comfyui-drama\output\gujing_3min\shots"
if not os.path.isdir(d):
    print("shots 目录不存在")
    sys.exit(0)
files = sorted(f for f in os.listdir(d) if f.endswith(".mp4"))
print(f"已生成 {len(files)}/45 个镜头:")
for f in files[-6:]:
    p = os.path.join(d, f)
    print(f"  {f}  {os.path.getsize(p)//1024} KB")
