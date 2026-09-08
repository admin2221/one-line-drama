# -*- coding: utf-8 -*-
"""drama_factory watchdog runner：由 schtasks 托管。

循环启动 drama_factory，若进程异常退出且未产出 final_drama.mp4 则自动重启
（--script-json + --resume 幂等：跳过已完成阶段）。最多尝试 20 次。
"""
import os
import subprocess
import sys
import time

LOG = r"D:\Comfyui\comfyui-drama\drama_run.log"
OUT_DIR = r"D:\Comfyui\comfyui-drama\output\techtest_8shot"
DONE_MARK = os.path.join(OUT_DIR, "final_drama.mp4")

cmd = [sys.executable, "-m", "factory.drama_factory",
       "--script-json", r"D:\Comfyui\comfyui-drama\output\techtest_8shot\script.json",
       "--target-seconds", "40",
       "--llm", "qwen3.8",
       "--megapixels", "0.2",
       "--steps", "16",
       "--no-enhance",
       "--output", OUT_DIR,
       "--resume"]

os.makedirs(OUT_DIR, exist_ok=True)
for attempt in range(1, 21):
    if os.path.exists(DONE_MARK):
        print("DONE: final_drama.mp4 exists", flush=True)
        sys.exit(0)
    print(f"=== attempt {attempt} start ===", flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        p = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT,
                             cwd=r"D:\Comfyui\comfyui-drama")
        print("drama_factory PID:", p.pid, flush=True)
        rc = p.wait()
    print(f"=== attempt {attempt} exit rc={rc} ===", flush=True)
    if os.path.exists(DONE_MARK):
        print("DONE: final_drama.mp4 exists", flush=True)
        sys.exit(0)
    time.sleep(5)
print("GAVE UP after 20 attempts", flush=True)
