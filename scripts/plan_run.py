# -*- coding: utf-8 -*-
"""plan-only wrapper：跑 drama_factory main 的 plan_only，输出到 plan_run.log。"""
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
STORY = ("深夜老书店即将拆迁，店主沈唐收到一本能照见亡者的旧日记；"
         "神秘女读者叶澜在书页夹缝发现真相，警探宋远追查一系列城市失踪案，"
         "三人于最后一夜在书店对峙，解开二十年前的旧案。")
OUT = r"D:\Comfyui\comfyui-drama\output\drama_3char_3min"
LOG = r"D:\Comfyui\comfyui-drama\plan_run.log"

cmd = [sys.executable, "-m", "factory.drama_factory", STORY,
       "--target-seconds", "165", "--llm", "qwen3.8",
       "--output", OUT, "--plan-only"]
with open(LOG, "w", encoding="utf-8") as f:
    p = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT,
                         cwd=r"D:\Comfyui\comfyui-drama")
    rc = p.wait()
print("plan-only exit rc:", rc)
print("log:", LOG)
