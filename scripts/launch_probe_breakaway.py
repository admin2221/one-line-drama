# -*- coding: utf-8 -*-
"""用 CREATE_BREAKAWAY_FROM_JOB 启动心跳探针，测试是否能脱离 Job 清理。"""
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
DETACHED = 0x00000008
NEW_GROUP = 0x00000200
BREAKAWAY = 0x01000000

p = subprocess.Popen(
    [r"D:\Comfyui\python\python.exe", r"D:\Comfyui\comfyui-drama\scripts\heartbeat_probe.py"],
    cwd=r"D:\Comfyui", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    creationflags=DETACHED | NEW_GROUP | BREAKAWAY)
print("probe PID:", p.pid)
