# -*- coding: utf-8 -*-
"""后台启动 drama_factory（plan-only 或完整流程），日志重定向到文件。"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
BASE = r"D:\Comfyui\comfyui-drama"
LOG = os.path.join(BASE, "drama_run.log")
ERR = os.path.join(BASE, "drama_run_err.log")

cmd = [r"D:\Comfyui\python\python.exe", "-m", "factory.drama_factory"]
cmd += sys.argv[1:]

with open(LOG, "w", encoding="utf-8") as fo, open(ERR, "w", encoding="utf-8") as fe:
    p = subprocess.Popen(cmd, stdout=fo, stderr=fe, cwd=BASE,
                         creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
print("launched PID:", p.pid)
print("cmd:", " ".join(cmd))
print("log:", LOG)
