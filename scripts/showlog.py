# -*- coding: utf-8 -*-
"""读取日志末尾 N 行，返回最新进度。"""
import sys

sys.stdout.reconfigure(encoding="utf-8")
path = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 1 else 10
lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
for ln in lines[-n:]:
    print(ln)
