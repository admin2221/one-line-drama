# -*- coding: utf-8 -*-
"""查今天(2026-08-22)的 Application Error / Hang / WER 崩溃事件。"""
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
query = (
    "wevtutil qe Application /q:"
    "*[System[(EventID=1000 or EventID=1001 or EventID=1002 or EventID=1005) "
    "and TimeCreated[@SystemTime>='2026-08-21T16:00:00.000Z']]]"
    "/c:8 /rd:true /f:text"
)
r = subprocess.run(query, capture_output=True, text=True, encoding="utf-8", errors="replace", shell=True)
print(r.stdout or r.stderr)
