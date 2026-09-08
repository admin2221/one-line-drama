# -*- coding: utf-8 -*-
"""都市职场逆袭 3 分钟短剧（3 角色 + 场景/物品参考图）watchdog runner。

由 schtasks 托管。走完整管线：LLM 分幕剧本(3角色/scenes/props) -> 多参考图 -> 逐镜头注入 -> ffmpeg。
断点续跑（--resume）。
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
LOG = r"D:\Comfyui\comfyui-drama\drama_workplace_run.log"
OUT_DIR = r"D:\Comfyui\comfyui-drama\output\drama_workplace_3min"
DONE_MARK = os.path.join(OUT_DIR, "final_drama.mp4")

STORY = ("小镇青年林逸初入摩天集团被上司王副总压榨、被心机同事赵琳抢夺功劳；"
         "他凭过硬能力与洞察在一次项目危机中力挽狂澜，当众揭露王副总挪用资金的内幕，"
         "董事长程总慧眼识才，林逸逆袭升任总监，赵琳幡然醒悟。")

cmd = [sys.executable, "-m", "factory.drama_factory",
       STORY,
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
