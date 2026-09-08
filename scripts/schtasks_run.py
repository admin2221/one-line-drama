# -*- coding: utf-8 -*-
"""创建并运行 schtasks 任务：drama_runner.py（完整 5 分钟短剧流程）。"""
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (r.stdout or "").strip() + ("\n" + (r.stderr or "").strip() if r.stderr else "")
    print("$", " ".join(cmd))
    print(out[:400] if out else f"(rc={r.returncode})")
    return r.returncode


TASK = "DramaFactory5min"
CMD = ('"D:\\Comfyui\\python\\python.exe" '
       '"D:\\Comfyui\\comfyui-drama\\scripts\\drama_runner.py"')

run(["schtasks", "/delete", "/tn", TASK, "/f"])
run(["schtasks", "/create", "/tn", TASK, "/tr", CMD, "/sc", "once", "/st", "00:00", "/f"])
run(["schtasks", "/run", "/tn", TASK])
