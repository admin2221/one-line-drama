# -*- coding: utf-8 -*-
"""补复制 pigking 成片与剧本到 G:\短剧项目。"""
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")
base = r"D:\Comfyui\comfyui-drama\output\drama_pigking_waste"
g_films = r"G:\短剧项目\成片\drama_pigking_waste"
g_scripts = r"G:\短剧项目\剧本\drama_pigking_waste"

final = os.path.join(base, "final_drama.mp4")
script = os.path.join(base, "script.json")
if os.path.isfile(final):
    os.makedirs(g_films, exist_ok=True)
    shutil.copy2(final, os.path.join(g_films, "final_drama.mp4"))
    print("成片已复制:", os.path.getsize(final), "bytes")
else:
    print("final_drama 缺失！")
if os.path.isfile(script):
    os.makedirs(g_scripts, exist_ok=True)
    shutil.copy2(script, os.path.join(g_scripts, "script.json"))
    print("剧本已复制")
