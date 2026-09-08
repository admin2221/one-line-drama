# -*- coding: utf-8 -*-
"""列出技能目录结构与文件。"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
base = r"C:\Users\Administrator\AppData\Roaming\com.chaitin.baizhi.monkeycode\ohmyagent\skills\drama-shorts-generator"
for root, dirs, files in os.walk(base):
    rel = os.path.relpath(root, base)
    print(f"[{rel}]")
    for f in files:
        p = os.path.join(root, f)
        print("   ", f, f"({os.path.getsize(p)}B)")
