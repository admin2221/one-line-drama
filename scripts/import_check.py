# -*- coding: utf-8 -*-
"""导入检查 drama_factory / generator。"""
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\Comfyui\comfyui-drama")
import factory.drama_factory as d
import factory.generator as g
print("import OK")
print("has _assemble_shot_refs:", hasattr(d, "_assemble_shot_refs"))
print("has _collect_scenes:", hasattr(d, "_collect_scenes"))
print("has _collect_props:", hasattr(d, "_collect_props"))
print("build_shot_video_prompt OK")
