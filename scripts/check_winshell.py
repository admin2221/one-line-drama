# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
try:
    import winshell
    print("winshell OK", winshell)
except Exception as e:
    print("NO winshell", e)
# 检查 powershell 可用
try:
    import subprocess
    r = subprocess.run(["powershell", "-NoProfile", "-Command", "echo ok"], capture_output=True, text=True, timeout=15)
    print("powershell rc", r.returncode, r.stdout.strip())
except Exception as e:
    print("ps err", e)
