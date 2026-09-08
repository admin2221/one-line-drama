# -*- coding: utf-8 -*-
"""清空 techtest_8shot 目录（除 script.json），强制全部重新生成。"""
import glob
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")
base = r"D:\Comfyui\comfyui-drama\output\techtest_8shot"
for f in glob.glob(os.path.join(base, "shots", "*.mp4")):
    os.remove(f)
    print("del", os.path.basename(f))
for f in ["character.png", "final_drama.mp4"]:
    p = os.path.join(base, f)
    if os.path.exists(p):
        os.remove(p)
        print("del", f)
print("清理完成，保留 script.json")
