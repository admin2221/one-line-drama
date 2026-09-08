# -*- coding: utf-8 -*-
"""用 schtasks 启动 ComfyUI（进程由 Task Scheduler 托管，脱离 Job 清理）。"""
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (r.stdout or "").strip() + ("\n" + (r.stderr or "").strip() if r.stderr else "")
    print("$", " ".join(cmd))
    print(out[:500] if out else f"(rc={r.returncode})")
    return r.returncode


TASK = "ComfyUI8188"
CMD = ('"D:\\Comfyui\\python\\python.exe" "D:\\Comfyui\\Comfyui\\main.py" '
       '--preview-method none --cuda-malloc --port 8188 --listen 0.0.0.0 '
       '--extra-model-paths-config "D:\\Comfyui\\Comfyui\\extra_model_paths.yaml"')

run(["schtasks", "/delete", "/tn", TASK, "/f"])
run(["schtasks", "/create", "/tn", TASK, "/tr", CMD, "/sc", "once", "/st", "00:00", "/f"])
run(["schtasks", "/run", "/tn", TASK])
