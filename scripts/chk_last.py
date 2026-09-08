# -*- coding: utf-8 -*-
"""检查 blk.64.ssm_conv1d.weight 等尾部张量的显式偏移 vs 文件大小。"""
import struct
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\Comfyui\Comfyui\custom_nodes\ComfyUI-llama-cpp_vlm\support")
import gguf_layers as gl

path = r"D:\Comfyui\Comfyui\models\LLM\Qwen3.8-27B-UD-Q4_K_S.gguf"
fsize = os.path.getsize(path)

with open(path, "rb") as f:
    head = f.read(24)
    version, n_tensors, n_kv = struct.unpack("<IQQ", head[4:24])
    for _ in range(n_kv):
        gl.read_string(f)
        gl.read_value(f)
    for i in range(n_tensors):
        name = gl.read_string(f)
        n_dims, = struct.unpack("<I", f.read(4))
        dims = list(struct.unpack(f"<{n_dims}Q", f.read(8 * n_dims)))
        ttype, = struct.unpack("<I", f.read(4))
        offset, = struct.unpack("<Q", f.read(8))
        if name.startswith("blk.64") or name in ("output.weight", "token_embd.weight", "output_norm.weight"):
            print(f"{name}: type={ttype} dims={dims} offset={offset:,} ({offset/1024**3:.3f} GiB)")

print(f"\n文件大小: {fsize:,} ({fsize/1024**3:.3f} GiB)")
