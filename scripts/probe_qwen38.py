# -*- coding: utf-8 -*-
"""尝试加载 Qwen3.8 GGUF（先 n_gpu_layers=0 纯 CPU 验证格式支持，再 GPU 验证显存）。"""
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
os.environ["PATH"] = (r"D:\Comfyui\python\Lib\site-packages\torch\lib" + ";" +
                      r"D:\Comfyui\python\Lib\site-packages\llama_cpp\lib" + ";" +
                      os.environ.get("PATH", ""))

import llama_cpp
print("llama_cpp:", llama_cpp.__version__)

from llama_cpp import Llama

path = r"D:\Comfyui\Comfyui\models\LLM\Qwen3.8-27B-UD-Q4_K_S.gguf"
mode = sys.argv[1] if len(sys.argv) > 1 else "cpu"
ctx = int(sys.argv[2]) if len(sys.argv) > 2 else 4096
layers = int(sys.argv[3]) if len(sys.argv) > 3 else 38
if mode == "cpu":
    kwargs = dict(model_path=path, n_gpu_layers=0, n_ctx=2048, verbose=True, use_mmap=False)
else:
    kwargs = dict(model_path=path, n_gpu_layers=layers, n_ctx=ctx, verbose=True, use_mmap=False)

t0 = time.time()
print(f"[{mode}] 加载中… (n_gpu_layers={kwargs['n_gpu_layers']}, n_ctx={kwargs['n_ctx']})")
try:
    llm = Llama(**kwargs)
    print(f"[{mode}] ✅ 加载成功 {time.time()-t0:.0f}s")
    out = llm.create_chat_completion(
        messages=[{"role": "user", "content": "用一句话介绍你自己。"}],
        max_tokens=64, temperature=0.7)
    print("回复:", out["choices"][0]["message"]["content"][:200])
except Exception as e:
    print(f"[{mode}] ❌ 失败: {type(e).__name__}: {e}")
    sys.exit(1)
