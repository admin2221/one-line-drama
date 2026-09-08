# -*- coding: utf-8 -*-
"""统计文件大小，打印尾部，检查是否含 JSON。"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
path = sys.argv[1]
with open(path, "rb") as f:
    raw = f.read()
t = raw.decode("utf-8", errors="replace")
print(f"bytes: {len(raw)}  chars: {len(t)}")
print("has <think>:", "<think>" in t)
print("--- tail 800 ---")
print(t[-800:])
