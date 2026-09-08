# -*- coding: utf-8 -*-
"""《刷牙变身！亚斯奥特曼大战巴巴尔星人》5分钟动画片。

3角色 + 场景/物品参考图 + 分镜衔接。watchdog runner，schtasks 托管。
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = r"D:\Comfyui\comfyui-drama"
LOG = r"D:\Comfyui\comfyui-drama\drama_ultraman_run.log"
OUT_DIR = r"D:\Comfyui\comfyui-drama\output\drama_ultraman_3min"
DONE_MARK = os.path.join(OUT_DIR, "final_drama.mp4")

STORY = ("一个6岁小朋友在一个平平无奇的清晨刷牙时，"
         "电动牙刷突然发出金光，他瞬间变身成守护和平的亚斯奥特曼。"
         "与此同时，邪恶的巴巴尔星人出现在城市上空大肆破坏，"
         "亚斯奥特曼飞身迎战，施展光线技与近身格斗，历经激战终于打败巴巴尔星人，"
         "变回小朋友结束了奇幻的一天。")

cmd = [sys.executable, "-m", "factory.drama_factory",
       STORY,
       "--target-seconds", "300",
       "--llm", "qwen3.5",
       "--megapixels", "0.2",
       "--steps", "16",
       "--characters-json", os.path.join(HERE, "characters", "ultraman_characters.json"),
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
