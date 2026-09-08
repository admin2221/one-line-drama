# -*- coding: utf-8 -*-
"""用 schtasks 启动 probe_outline_q35.py（输出到 probe_q35_out.txt）。"""
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")


def run(cmd):
    subprocess.run(cmd, capture_output=True, text=True,
                   encoding="utf-8", errors="replace")


TASK = "ProbeQ35"
CMD = ('"D:\\Comfyui\\python\\python.exe" '
       '"D:\\Comfyui\\comfyui-drama\\scripts\\probe_outline_q35.py"')
run(["schtasks", "/delete", "/tn", TASK, "/f"])
run(["schtasks", "/create", "/tn", TASK, "/tr", CMD, "/sc", "once", "/st", "00:00", "/f"])
run(["schtasks", "/run", "/tn", TASK])
print("probe q35 submitted")
