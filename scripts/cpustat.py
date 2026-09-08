# -*- coding: utf-8 -*-
"""CPU 与内存占用检查。"""
import sys

sys.stdout.reconfigure(encoding="utf-8")
import psutil

print("CPU%:", psutil.cpu_percent(interval=1))
vm = psutil.virtual_memory()
print(f"RAM used: {vm.used/1e9:.1f}G / {vm.total/1e9:.1f}G ({vm.percent}%)")
for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
    try:
        if p.info["name"] and "python" in p.info["name"].lower():
            rss = p.info["memory_info"].rss / 1e6
            if rss > 100:
                print(f"  PID {p.info['pid']} CPU {p.info['cpu_percent']:5.1f}% RSS {rss:.0f}MB")
    except Exception:
        pass
