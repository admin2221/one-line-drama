# -*- coding: utf-8 -*-
"""最小验证：提交 qwen3.8 短 prompt（vram_limit=21 → 61 层），确认 ComfyUI 是否存活完成。

用法：python submit_min.py [vram_limit] [max_tokens]
"""
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\Comfyui\comfyui-drama")

from factory.client import ComfyClient
from factory import generator

vram = int(sys.argv[1]) if len(sys.argv) > 1 else 21
max_tokens = int(sys.argv[2]) if len(sys.argv) > 2 else 200

client = ComfyClient()
print("health:", client.health().get("comfyui_version"))
print(f"提交: vram_limit={vram}, max_tokens={max_tokens}")

# 临时覆盖 qwen3.8 的 vram_limit
import factory.generator as g
g.LLM_CONFIGS["qwen3.8"]["vram_limit"] = vram

api = g.build_script_prompt("讲一个 200 字的小故事。", "你是讲故事的人。",
                            max_tokens=max_tokens, llm="qwen3.8")
t0 = time.time()
try:
    text = __import__("factory.drama_factory", fromlist=["run_and_get_text"]).run_and_get_text(client, api)
    print(f"=== 完成（{time.time()-t0:.0f}s）===")
    print("长度:", len(text) if text else 0)
    print("内容:", (text or "")[:150])
except Exception as e:
    print(f"!!! 失败: {type(e).__name__}: {e}")
