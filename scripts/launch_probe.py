# -*- coding: utf-8 -*-
"""对照实验：用 launch_drama.py 同款 Popen 启动 sleep 进程，写心跳文件。"""
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
HEARTBEAT = r"D:\Comfyui\comfyui-drama\scripts\watchdog_heartbeat.txt"
code = (
    "import time\n"
    "with open(r'D:/Comfyui/comfyui-drama/scripts/watchdog_heartbeat.txt','w') as f:\n"
    "    f.write('alive '+str(int(time.time())))\n"
    "time.sleep(120)\n"
)
with open(r"D:\Comfyui\comfyui-drama\scripts\sleep_probe.py", "w") as f:
    f.write(code)
p = subprocess.Popen(
    [r"D:\Comfyui\python\python.exe", r"D:\Comfyui\comfyui-drama\scripts\heartbeat_probe.py"],
    cwd=r"D:\Comfyui", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
print("probe PID:", p.pid)
