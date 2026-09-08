# -*- coding: utf-8 -*-
"""验证 qwen3.8 关闭思考后能直接输出合法 JSON。"""
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\Comfyui\comfyui-drama")

from factory.client import ComfyClient
from factory.drama_factory import run_and_get_text
from factory import generator

client = ComfyClient()
api = generator.build_script_prompt(
    "讲一个关于灯塔守夜人的小故事。", "你是编剧，输出 JSON：{\"title\": \"标题\", \"character\": \"角色描述\", \"style\": \"风格\", \"shots\": [{\"shot\": 1, \"scene\": \"场景\", \"duration\": \"5\", \"prompt\": \"画面描述\"}]}",
    max_tokens=600, llm="qwen3.8")
text = run_and_get_text(client, api)
print("=== 原始输出 ===")
print(text[:1200])
print("=== 检查 ===")
print("含<think>:", "<think>" in text)
start, end = text.find("{"), text.rfind("}")
print("JSON可解析:", end > start > -1 and bool(__import__("factory.drama_factory", fromlist=["parse_json_block"]).parse_json_block(text)))
