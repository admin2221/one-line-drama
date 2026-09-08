# -*- coding: utf-8 -*-
import sys, os
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\Comfyui\Comfyui\custom_nodes\ComfyUI-llama-cpp_vlm\support")
from gguf_layers import get_layer_count

path = r"D:\Comfyui\Comfyui\models\LLM\Qwen3.8-27B-UD-Q4_K_S.gguf"
layers = get_layer_count(path)
size = os.path.getsize(path)
print("getsize:", size, f"({size/1024**3:.2f} GiB)")
print("layer_count:", layers)
if layers:
    gsize = size * 1.55 / (1024 ** 3)
    gl = gsize / layers
    print(f"gguf_size={gsize:.2f} GiB (x1.55), gguf_layer_size={gl:.4f}")
    for v in (13, 14, 15, 16, 20, 22):
        print(f"  vram_limit={v} -> n_gpu_layers={max(1, int(v/gl))}")
