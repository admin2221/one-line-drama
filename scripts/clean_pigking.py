# -*- coding: utf-8 -*-
"""清空 drama_pigking_waste 全部内容，强制全新生成（含剧本，重建角色名归一化）。"""
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")
base = r"D:\Comfyui\comfyui-drama\output\drama_pigking_waste"
if os.path.isdir(base):
    shutil.rmtree(base)
os.makedirs(base)
print("cleaned drama_pigking_waste")
