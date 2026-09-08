# -*- coding: utf-8 -*-
"""检查 GPU 利用率与占用进程。"""
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
r = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,used_gpu_memory",
                    "--format=csv,noheader"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print("compute apps:", r.stdout.strip() or "(none)")
r2 = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used",
                     "--format=csv,noheader"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
print("gpu:", r2.stdout.strip())
