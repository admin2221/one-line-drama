# -*- coding: utf-8 -*-
import os, sys
sys.stdout.reconfigure(encoding="utf-8")
hits = []
for root, dirs, files in os.walk(r"D:\Comfyui"):
    for fn in files:
        if "qwen3.8" in fn.lower():
            p = os.path.join(root, fn)
            try:
                hits.append((os.path.getsize(p), p))
            except OSError:
                pass
hits.sort(reverse=True)
for sz, p in hits:
    print(f"{sz:,}  {p}")
if not hits:
    print("D:\\Comfyui 下无其他 Qwen3.8 文件")
