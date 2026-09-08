# -*- coding: utf-8 -*-
"""轮询 run.log 并显示最新 N 行（自动等待间隔）。"""
import os
import sys
import time

LOG = r"D:\Comfyui\comfyui-drama\output\gujing_3min\run.log"

def show(tail=12):
    if not os.path.exists(LOG):
        print("[日志尚未创建]")
        return
    with open(LOG, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    for ln in lines[-tail:]:
        print(ln)

if __name__ == "__main__":
    wait = float(sys.argv[1]) if len(sys.argv) > 1 else 0
    tail = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    if wait:
        time.sleep(wait)
    show(tail)
