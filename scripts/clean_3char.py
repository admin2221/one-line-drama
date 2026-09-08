# -*- coding: utf-8 -*-
"""清空 drama_3char_3min 的参考图与镜头（保留 script.json），强制重新生成图文视频。"""
import glob
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
base = r"D:\Comfyui\comfyui-drama\output\drama_3char_3min"
os.makedirs(base, exist_ok=True)
for f in glob.glob(os.path.join(base, "shots", "*.mp4")):
    os.remove(f)
for f in glob.glob(os.path.join(base, "*.png")):
    os.remove(f)
for f in ["final_drama.mp4"]:
    p = os.path.join(base, f)
    if os.path.exists(p):
        os.remove(p)
print("cleaned reference images + shots, kept script.json")
