# -*- coding: utf-8 -*-
"""分离启动 test_qwen38_long.py，输出到 test_long.log（进程与工具调用解耦）。"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
BASE = r"D:\Comfyui"
SCRIPT = os.path.join(BASE, "comfyui-drama", "scripts", "test_qwen38_long.py")
OUT = os.path.join(BASE, "comfyui-drama", "scripts", "test_long.log")
ERR = os.path.join(BASE, "comfyui-drama", "scripts", "test_long_err.log")

with open(OUT, "w", encoding="utf-8") as fo, open(ERR, "w", encoding="utf-8") as fe:
    p = subprocess.Popen(
        [r"D:\Comfyui\python\python.exe", SCRIPT],
        stdout=fo, stderr=fe, cwd=BASE,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
print("launched PID:", p.pid)
print("log:", OUT)
