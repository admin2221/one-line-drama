# -*- coding: utf-8 -*-
"""用 ctypes 调 nvml 或 nvidia-smi --query 获取各 PID 显存。"""
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
r = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,used_memory",
                    "--format=csv,noheader"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print(r.stdout or r.stderr)
