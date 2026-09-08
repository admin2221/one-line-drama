# -*- coding: utf-8 -*-
"""端到端最小测试：只跑剧本 LLM 阶段，验证输出提取与 JSON 解析。"""
import sys
import os
sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, r"D:\Comfyui\comfyui-drama")
from factory.client import ComfyClient
from factory.drama_factory import parse_json_block, run_and_get_text
from factory import generator
from factory.prompts import SCRIPT_DIRECTOR_PROMPT

STORY = "一个外卖小哥深夜送餐，意外救下被追杀的富家千金，从此卷入豪门恩怨。"

client = ComfyClient()
print("health:", client.health().get("comfyui_version"))

print("提交剧本 LLM 请求…")
api = generator.build_script_prompt(STORY, SCRIPT_DIRECTOR_PROMPT)
text = run_and_get_text(client, api)
print("=== LLM 原始输出（前 600 字）===")
print((text or "")[:600])
print("=== 输出长度:", len(text or ""), "===")

script = parse_json_block(text)
if script:
    print("=== 解析成功 ===")
    print("title:", script.get("title"))
    print("character:", script.get("character"))
    print("style:", script.get("style"))
    print("镜头数:", len(script.get("shots", [])))
    for s in script["shots"][:3]:
        print("  shot", s.get("shot"), "| scene:", s.get("scene"), "| dur:", s.get("duration"),
              "| img_prompt:", (s.get("image_prompt") or "")[:50])
else:
    print("!!! JSON 解析失败")
    sys.exit(1)
