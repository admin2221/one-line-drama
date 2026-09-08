# -*- coding: utf-8 -*-
"""列出 dist\drama-cli 产物及大小。"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
base = r"D:\Comfyui\comfyui-drama\dist\drama-cli"
files = os.listdir(base)
for f in files:
    p = os.path.join(base, f)
    print(f"{f}: {os.path.getsize(p)} bytes")
