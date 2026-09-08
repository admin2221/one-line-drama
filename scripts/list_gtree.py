# -*- coding: utf-8 -*-
"""列出 G:\短剧项目 目录树（一层）。"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
base = r"G:\短剧项目"
for root, dirs, files in os.walk(base):
    depth = os.path.relpath(root, base).count(os.sep)
    ind = "  " * depth
    print(f"{ind}{os.path.basename(root)}/")
    for f in files:
        p = os.path.join(root, f)
        sz = os.path.getsize(p)
        print(f"{ind}  {f} ({sz/1024/1024:.1f}MB)" if sz > 1024 * 1024 else f"{ind}  {f} ({sz} B)")
    if depth >= 1:
        dirs[:] = []
