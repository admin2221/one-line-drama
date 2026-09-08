# -*- coding: utf-8 -*-
"""后台启动短剧工厂全量生成（detached 进程，日志写入 run.log）。"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

BASE = r"D:\Comfyui"
OUT = r"D:\Comfyui\comfyui-drama\output\gujing_3min"
LOG = os.path.join(OUT, "run.log")
SCRIPT = r"D:\Comfyui\comfyui-drama\factory\drama_factory.py"

args = [
    sys.executable, SCRIPT,
    "--script-json", os.path.join(OUT, "script.json"),
    "--output", OUT,
    "--resume",
]

with open(LOG, "w", encoding="utf-8") as f:
    p = subprocess.Popen(
        args, stdout=f, stderr=subprocess.STDOUT,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        cwd=BASE,
    )
print("后台进程 PID:", p.pid)
print("日志:", LOG)
