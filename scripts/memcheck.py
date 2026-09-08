# -*- coding: utf-8 -*-
"""查看指定进程的显存占用。"""
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
r = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,process_name,used_gpu_memory",
                    "--format=csv,noheader"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
target = sys.argv[1] if len(sys.argv) > 1 else None
for line in r.stdout.strip().splitlines():
    if target and target not in line:
        continue
    print(line)
