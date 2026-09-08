# -*- coding: utf-8 -*-
"""用 schtasks 启动养猪小伙逆袭短剧流程。"""
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (r.stdout or "").strip() + ("\n" + (r.stderr or "").strip() if r.stderr else "")
    print("$", " ".join(cmd))
    print(out[:300] if out else f"(rc={r.returncode})")


TASK = "DramaPigkingWaste"
CMD = ('"D:\\Comfyui\\python\\python.exe" '
       '"D:\\Comfyui\\comfyui-drama\\scripts\\drama_pigking_runner.py"')
run(["schtasks", "/delete", "/tn", TASK, "/f"])
run(["schtasks", "/create", "/tn", TASK, "/tr", CMD, "/sc", "once", "/st", "00:00", "/f"])
run(["schtasks", "/run", "/tn", TASK])
print("drama_pigking started")
