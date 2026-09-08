# -*- coding: utf-8 -*-
"""完整 3 分钟短剧（3 角色 + 场景/物品参考图）watchdog runner。

由 schtasks 托管。story + stage 文案走完整管线：
  LLM 分幕剧本(3角色/scenes/props) -> 多参考图生成 -> 逐镜头注入 -> ffmpeg 拼接。
若进程异常退出且未产出 final_drama.mp4 则自动重启（--resume 幂等）。
"""
import os
import subprocess
import sys

LOG = r"D:\Comfyui\comfyui-drama\drama_3min_run.log"
OUT_DIR = r"D:\Comfyui\comfyui-drama\output\drama_3char_3min"
DONE_MARK = os.path.join(OUT_DIR, "final_drama.mp4")

STORY = ("深夜老书店即将拆迁，店主沈唐收到一本能照见亡者的旧日记；"
         "神秘女读者叶澜在书页夹缝发现真相，警探宋远追查一系列城市失踪案，"
         "三人于最后一夜在书店对峙，解开二十年前的旧案。")

cmd = [sys.executable, "-m", "factory.drama_factory",
       "--script-json", os.path.join(OUT_DIR, "script.json"),
       "--target-seconds", "165",
       "--llm", "qwen3.5",
       "--megapixels", "0.2",
       "--steps", "16",
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
    import time
    time.sleep(5)
print("GAVE UP after 20 attempts", flush=True)
