# -*- coding: utf-8 -*-
"""杀掉所有 drama_runner / drama_factory 进程。"""
import sys

sys.stdout.reconfigure(encoding="utf-8")
import psutil

for p in psutil.process_iter(["pid", "cmdline"]):
    cl = " ".join(p.info["cmdline"] or [])
    if "drama_runner" in cl or "factory.drama_factory" in cl:
        print("kill PID", p.info["pid"])
        p.kill()
print("done")
