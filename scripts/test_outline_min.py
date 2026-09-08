# -*- coding: utf-8 -*-
"""小规模总纲测试：4 幕，验证 reasoning_budget=0 + temp 0.2 + 强约束后 JSON 输出。"""
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\Comfyui\comfyui-drama")

from factory.client import ComfyClient
from factory.drama_factory import run_and_get_text, parse_json_block
from factory import generator
from factory.prompts import outline_system_prompt

client = ComfyClient()
story = "暴雨夜外卖骑手陈默送快递到老宅，开门的竟是失踪十年的哥哥陈影，门外黑衣人逼近。"
api = generator.build_outline_prompt(story, 60, 15, 4, llm="qwen3.8")
text = run_and_get_text(client, api)
print("=== 输出统计 ===")
print("chars:", len(text or ""))
print("has <think>:", "<think>" in (text or ""))
parsed = parse_json_block(text or "")
print("JSON 可解析:", bool(parsed))
if parsed:
    print("title:", parsed.get("title"))
    print("beats 数:", len(parsed.get("beats", [])))
    print("character:", parsed.get("character", "")[:80])
    print("style:", parsed.get("style", "")[:60])
else:
    print("=== 输出前 300 字 ===")
    print((text or "")[:300])
    print("=== 输出后 300 字 ===")
    print((text or "")[-300:])
