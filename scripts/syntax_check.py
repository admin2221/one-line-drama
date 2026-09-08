# -*- coding: utf-8 -*-
"""语法检查 runner 脚本。"""
import ast
import sys

sys.stdout.reconfigure(encoding="utf-8")
for p in [r"D:\Comfyui\comfyui-drama\scripts\drama_workplace_runner.py",
          r"D:\Comfyui\comfyui-drama\scripts\drama_3char_runner.py",
          r"D:\Comfyui\comfyui-drama\scripts\drama_wusu_runner.py",
          r"D:\Comfyui\comfyui-drama\scripts\drama_ultraman_runner.py",
          r"D:\Comfyui\comfyui-drama\scripts\drama_pigking_runner.py"]:
    try:
        ast.parse(open(p, encoding="utf-8").read())
        print("OK", p.split("\\")[-1])
    except SyntaxError as e:
        print("SYNTAX-ERR", p, e)
