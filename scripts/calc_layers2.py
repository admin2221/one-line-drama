# -*- coding: utf-8 -*-
import sys, os
sys.stdout.reconfigure(encoding="utf-8")
from gguf import GGUFReader

MODEL = r"D:\Comfyui\Comfyui\models\LLM\Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-IQ3_M.gguf"
r = GGUFReader(MODEL)
bc = None
for k, f in r.fields.items():
    if k.endswith(".block_count"):
        try: bc = (f.parts[0] if hasattr(f.parts[0],'tolist') else f.contents)[0]
        except Exception: bc = f.contents
        break
if bc is None:
    try: bc = r.get_field("llama.block_count")
    except Exception: bc = None
print("block_count:", bc)
gguf_layers = int(bc) or 32
vram_factor = 1.55
size_gb = os.path.getsize(MODEL) * vram_factor / (1024**3)
layer_size = size_gb / gguf_layers
print("est size(factor1.55): %.2f GB | per-layer: %.4f GB" % (size_gb, layer_size))
for vl in (12, 14, 15, 16):
    print(f"  vram_limit={vl} → n_gpu_layers={max(1,int(vl/layer_size))}")
