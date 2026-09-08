# -*- coding: utf-8 -*-
"""最小复现：提交一次总纲 LLM API，打印完整 error（exception_type/message）。"""
import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\Comfyui\comfyui-drama")
from factory.client import ComfyClient
import factory.generator as g

STORY = ("深夜老书店即将拆迁，店主沈唐收到一本能照见亡者的旧日记；"
         "神秘女读者叶澜在书页夹缝发现真相，警探宋远追查一系列城市失踪案，"
         "三人于最后一夜在书店对峙，解开二十年前的旧案。")

client = ComfyClient(base_url="http://127.0.0.1:8188")
api = g.build_outline_prompt(STORY, 165, 41, 10, llm="qwen3.8", n_char=3)
pid = client.queue_prompt(api)["prompt_id"]
print("submitted pid:", pid, flush=True)
# 不 wait_done；任务在 ComfyUI 队列后台执行，稍后用 show_msgs.py 查 history
