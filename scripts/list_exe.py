# -*- coding: utf-8 -*-
"""列出 G:\短剧项目\成品安装包 内容。"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
base = r"G:\短剧项目\成品安装包"
for root, dirs, files in os.walk(base):
    rel = os.path.relpath(root, base)
    print(f"[{rel}]")
    for f in files:
        p = os.path.join(root, f)
        print("   ", f, f"({os.path.getsize(p)/1024/1024:.1f}MB)" if os.path.getsize(p) > 1024*1024 else f"({os.path.getsize(p)}B)")
    if len(os.listdir(root)) > 30 and rel != ".":
        dirs[:] = []
