# -*- coding: utf-8 -*-
"""列出所有 drama_factory / drama_runner / main.py 进程。"""
import sys

sys.stdout.reconfigure(encoding="utf-8")
import psutil

for p in psutil.process_iter(["pid", "create_time", "cmdline"]):
    cl = " ".join(p.info["cmdline"] or [])
    if "drama_factory" in cl or "drama_runner" in cl or " main.py" in cl:
        import datetime
        t = datetime.datetime.fromtimestamp(p.info["create_time"]).strftime("%H:%M:%S")
        print(f"PID {p.info['pid']} 起于{t}  {cl[:120]}")
