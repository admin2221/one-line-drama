# -*- coding: utf-8 -*-
"""校验 G:\短剧项目 完整结构。"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
base = r"G:\短剧项目"
print("=== G:\\短剧项目 顶层 ===")
for d in sorted(os.listdir(base)):
    p = os.path.join(base, d)
    print("  ", d + "/" if os.path.isdir(p) else d)

print("\n=== 成片（final_drama.mp4 汇总）===")
films_dir = os.path.join(base, "成片")
for d in sorted(os.listdir(films_dir)):
    f = os.path.join(films_dir, d, "final_drama.mp4")
    if os.path.isfile(f):
        print(f"  {d}: {os.path.getsize(f)/1024/1024:.1f}MB")
    else:
        print(f"  {d}: 缺成片")

import subprocess
r = subprocess.run(["D:\\Comfyui\\python\\python.exe", "-m", "PyInstaller", "--version"],
                   capture_output=True, text=True, errors="replace")
print("\npigking 成片在 G 盘确认:", os.path.isfile(os.path.join(films_dir, "drama_pigking_waste", "final_drama.mp4")))
