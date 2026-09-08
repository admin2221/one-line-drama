# -*- coding: utf-8 -*-
import sys, os
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\Comfyui\Comfyui\custom_nodes\XB_ToolBox")
from support_llama import get_layer_count

MODEL = r"D:\Comfyui\Comfyui\models\LLM\Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-IQ3_M.gguf"
vram_factor = 1.55
gguf_layers = get_layer_count(MODEL) or 32
size_gb = os.path.getsize(MODEL) * vram_factor / (1024**3)
layer_size = size_gb / gguf_layers
print("layers:", gguf_layers, "| est size(factor1.55): %.2f GB" % size_gb,
      "| per-layer: %.4f GB" % layer_size)
for vl in (12, 14, 15, 16):
    n = max(1, int(vl / layer_size))
    print(f"  vram_limit={vl} → n_gpu_layers={n}")
