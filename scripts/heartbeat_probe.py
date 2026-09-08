# -*- coding: utf-8 -*-
"""循环心跳探针：每 5s 写一次心跳，持续 300s。用于验证 DETACHED 进程跨调用存活。"""
import time

HEARTBEAT = r"D:\Comfyui\comfyui-drama\scripts\probe_heartbeat.txt"
for i in range(60):
    with open(HEARTBEAT, "w") as f:
        f.write(f"tick={i} ts={int(time.time())}")
    time.sleep(5)
with open(HEARTBEAT, "w") as f:
    f.write("DONE")
