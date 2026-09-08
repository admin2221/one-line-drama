# -*- coding: utf-8 -*-
"""用 schtasks 创建并运行计划任务（进程由 Task Scheduler 托管，脱离 Job）。"""
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    print("$", " ".join(cmd))
    out = (r.stdout or "").strip() + ("\n" + (r.stderr or "").strip() if r.stderr else "")
    print(out[:500] if out else f"(rc={r.returncode})")
    return r.returncode


TASK = "DramaTaskHB"
CMD = '"D:\\Comfyui\\python\\python.exe" "D:\\Comfyui\\comfyui-drama\\scripts\\heartbeat_probe.py"'

run(["schtasks", "/delete", "/tn", TASK, "/f"])
run(["schtasks", "/create", "/tn", TASK, "/tr", CMD, "/sc", "once", "/st", "00:00", "/f"])
run(["schtasks", "/run", "/tn", TASK])
