# -*- coding: utf-8 -*-
"""《五俗历险记》校园搞笑剧：5 俗神仙下凡，5角色+场景/物品参考图+分镜衔接。

watchdog runner，由 schtasks 托管。qwen3.5 分幕剧本 -> 多参考图 -> 逐镜头注入(带衔接) -> ffmpeg。
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = r"D:\Comfyui\comfyui-drama"
LOG = r"D:\Comfyui\comfyui-drama\drama_wusu_run.log"
OUT_DIR = r"D:\Comfyui\comfyui-drama\output\drama_wusu_3min"
DONE_MARK = os.path.join(OUT_DIR, "final_drama.mp4")

STORY = ("《五俗历险记》：天庭五位因各犯【贪吃、懒惰、傲慢、急躁、财迷】五俗被贬到凡间的神仙，"
         "投胎成五名性格迥异的大学新生，在同一所大学经历爆笑历练——"
         "抢食堂、逃早课、社团恶作剧、final考试风暴、帮同学破解校园怪谈，"
         "在啼笑皆非中渐渐领悟五俗皆空，最终修回正果重返天界。")

cmd = [sys.executable, "-m", "factory.drama_factory",
       STORY,
       "--target-seconds", "300",
       "--llm", "qwen3.5",
       "--megapixels", "0.2",
       "--steps", "16",
       "--characters-json", os.path.join(HERE, "characters", "wusu_characters.json"),
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
