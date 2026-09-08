# -*- coding: utf-8 -*-
"""列出所有 python 进程及命令行，定位 drama_factory。"""
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
r = subprocess.run(["tasklist", "/V", "/FO", "CSV"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
for line in (r.stdout or "").splitlines():
    if "python" in line.lower() or "pythonw" in line.lower():
        print(line.split(",")[0], "|", line)
