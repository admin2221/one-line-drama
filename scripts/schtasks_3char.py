# -*- coding: utf-8 -*-
"""用 schtasks 启动完整 3 角色 3 分钟短剧流程（watchdog runner）。"""
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (r.stdout or "").strip() + ("\n" + (r.stderr or "").strip() if r.stderr else "")
    print("$", " ".join(cmd))
    print(out[:300] if out else f"(rc={r.returncode})")


TASK = "Drama3char3min"
CMD = ('"D:\\Comfyui\\python\\python.exe" '
       '"D:\\Comfyui\\comfyui-drama\\scripts\\drama_3char_runner.py"')
run(["schtasks", "/delete", "/tn", TASK, "/f"])
run(["schtasks", "/create", "/tn", TASK, "/tr", CMD, "/sc", "once", "/st", "00:00", "/f"])
run(["schtasks", "/run", "/tn", TASK])
print("drama3char started")
