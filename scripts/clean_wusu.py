# -*- coding: utf-8 -*-
"""清空 drama_wusu_3min 全部内容，强制全新生成（含剧本）。"""
import glob
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")
base = r"D:\Comfyui\comfyui-drama\output\drama_wusu_3min"
if os.path.isdir(base):
    shutil.rmtree(base)
os.makedirs(base)
print("cleaned drama_wusu_3min")
