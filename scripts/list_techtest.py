# -*- coding: utf-8 -*-
"""列出 techtest_8shot 完整产物。"""
import glob
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
base = r"D:\Comfyui\comfyui-drama\output\techtest_8shot"
print("=== techtest_8shot ===")
print("final_drama.mp4:", os.path.getsize(os.path.join(base, "final_drama.mp4")) if os.path.exists(os.path.join(base, "final_drama.mp4")) else "缺失")
print("character.png:", os.path.getsize(os.path.join(base, "character.png")) if os.path.exists(os.path.join(base, "character.png")) else "缺失")
shots = glob.glob(os.path.join(base, "shots", "*.mp4"))
print(f"shots: {len(shots)} 个")
sizes = sorted(os.path.getsize(s) for s in shots)
print("镜头大小范围:", sizes[0] if sizes else "-", "-", sizes[-1] if sizes else "-", "字节")
print("shot文件名:", [os.path.basename(s) for s in sorted(shots)])
