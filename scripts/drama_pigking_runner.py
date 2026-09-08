# -*- coding: utf-8 -*-
"""《猪王逆袭：都市首富败局》都市言情逆天反转短剧。

3主角 + 场景/物品参考图 + 分镜衔接 + 独立输出文件夹。watchdog，schtasks 托管。
时长 8-10 分钟（target-seconds 540）。
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = r"D:\Comfyui\comfyui-drama"
LOG = r"D:\Comfyui\comfyui-drama\drama_pigking_run.log"
OUT_DIR = r"D:\Comfyui\comfyui-drama\output\drama_pigking_waste"
DONE_MARK = os.path.join(OUT_DIR, "final_drama.mp4")

STORY = (
    "【爆款开局钩子】多年后被人看不起的养猪小伙「猪王」回到都市，"
    "竟是隐藏的顶级养殖业专家。他对首富钱总的下手了——"
    "先是钱总当众羞辱他、砸掉他的猪场赔偿款，"
    "猪王却凭借超凡的专业眼光与商业谋略，在钱总最骄傲的生猪期货与酒店餐饮帝国上连环反击，"
    "一步步击败首富。首富千金钱可馨从误会、好奇到倾心，"
    "猪王在商战巅峰对决中完胜钱总，成为新首富，最终迎娶钱可馨为娇妻，"
    "完成逆天反转的爽文结局。")

# 若已有剧本，复用（--script-json），配合 --resume 从中断镜头续跑
script_json = os.path.join(OUT_DIR, "script.json")

cmd = [sys.executable, "-m", "factory.drama_factory",
       STORY,
       "--target-seconds", "540",
       "--llm", "qwen3.5",
       "--megapixels", "0.2",
       "--steps", "16",
       "--characters-json", os.path.join(HERE, "characters", "pigking_characters.json"),
       "--output", OUT_DIR,
       "--resume"]
if os.path.isfile(script_json):
    cmd += ["--script-json", script_json]
    print("复用已有剧本:", script_json, flush=True)

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
