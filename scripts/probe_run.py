# -*- coding: utf-8 -*-
"""用 schtasks 启动 probe_outline.py 并把输出重定向到 probe_out.log。"""
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
LOG = r"D:\Comfyui\comfyui-drama\probe_out.log"
with open(LOG, "w", encoding="utf-8") as f:
    p = subprocess.Popen(
        [sys.executable, r"D:\Comfyui\comfyui-drama\scripts\probe_outline.py"],
        stdout=f, stderr=subprocess.STDOUT, cwd=r"D:\Comfyui\comfyui-drama")
    print("probe PID:", p.pid)
    rc = p.wait()
    print("probe exit:", rc)
