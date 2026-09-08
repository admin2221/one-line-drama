# -*- coding: utf-8 -*-
"""列出 G:\短剧项目\成品安装包 完整结构。"""
import os
import sys
sys.stdout.reconfigure(encoding="utf-8")
base = r"G:\短剧项目\成品安装包"
for root, dirs, files in os.walk(base):
    rel = os.path.relpath(root, base)
    print(f"\n[{rel}]")
    for f in sorted(files):
        p = os.path.join(root, f)
        sz = os.path.getsize(p) / 1024 / 1024
        print(f"   {f}  ({sz:.1f}MB)" if sz > 0.1 else f"   {f}  ({os.path.getsize(p)}B)")
