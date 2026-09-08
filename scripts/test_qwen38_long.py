# -*- coding: utf-8 -*-
"""验证 qwen3.8 推理 + 突破 4096 max_tokens 限制。

通过 ComfyUI API 提交长输出任务（max_tokens=12000），验证：
1. 不再返回 400 校验错误（旧版 4096 上限）
2. 实际生成 > 4096 token 的输出
"""
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\Comfyui\comfyui-drama")

from factory.client import ComfyClient
from factory.drama_factory import run_and_get_text
from factory import generator

client = ComfyClient()
print("health:", client.health().get("comfyui_version"))

SYSTEM = "你是一个讲故事的高手。"
USER = "请用中文写一个完整的短篇故事，要有起承转合、人物和细节，内容尽量长（目标 6000 字以上），不要提前结束，故事讲完整。"

api = generator.build_script_prompt(USER, SYSTEM, max_tokens=12000, llm="qwen3.8")
# build_script_prompt 的 custom_prompt 就是 story 参数
t0 = time.time()
print("提交 qwen3.8 长输出任务（max_tokens=12000）…")
text = run_and_get_text(client, api)
elapsed = time.time() - t0

if not text:
    print("!!! 无输出")
    sys.exit(1)

print(f"=== 生成完成（{elapsed:.0f}s）===")
print(f"字符数: {len(text)}")
print(f"前 200 字: {text[:200]}")

# 粗估 token 数（中文约 1 token/字）
est_tokens = len(text)
print(f"估算 token 数: ~{est_tokens}")
if est_tokens > 4096:
    print("✅ 已突破 4096 限制！")
else:
    print("⚠️ 输出未超过 4096 token（模型可能提前收尾），但 400 校验错误已消除")
