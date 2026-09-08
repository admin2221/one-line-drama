# -*- coding: utf-8 -*-
"""快速探针：用 qwen3.8ag 跑一个极短 prompt，测加载+推理速度。
"""
import sys, time
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\Comfyui\comfyui-drama")
from factory import generator
from factory.client import ComfyClient
from factory.drama_factory import run_and_get_text

BASE = "http://127.0.0.1:8188"
client = ComfyClient(BASE)

# 构建一个极短的 LLM 调用（无系统提示，两三句话）
api = generator.build_script_prompt("一句话回答：你好。", "你是一个助手，请简短回答。",
                                    max_tokens=200, llm="qwen3.8ag")
print("开始加载 qwen3.8ag（首次加载较慢）…")
t0 = time.time()
text = run_and_get_text(client, api)
dt = time.time() - t0
print(f"耗时 {dt:.0f}s，返回: {text!r}")
