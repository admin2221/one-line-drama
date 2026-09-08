# -*- coding: utf-8 -*-
"""用 gguf.GGML_QUANT_SIZES 精确计算数据区终点，判定文件是否完整。"""
import struct
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\Comfyui\Comfyui\custom_nodes\ComfyUI-llama-cpp_vlm\support")
import gguf_layers as gl
from gguf.constants import GGML_QUANT_SIZES

path = r"D:\Comfyui\Comfyui\models\LLM\Qwen3.8-27B-UD-Q4_K_S.gguf"
fsize = os.path.getsize(path)
print(f"文件大小: {fsize:,} ({fsize/1024**3:.3f} GiB)")

with open(path, "rb") as f:
    head = f.read(24)
    version, n_tensors, n_kv = struct.unpack("<IQQ", head[4:24])
    for _ in range(n_kv):
        gl.read_string(f)
        gl.read_value(f)

    max_end = 0
    bad = []
    for i in range(n_tensors):
        name = gl.read_string(f)
        n_dims, = struct.unpack("<I", f.read(4))
        dims = list(struct.unpack(f"<{n_dims}Q", f.read(8 * n_dims)))
        ttype, = struct.unpack("<I", f.read(4))
        offset, = struct.unpack("<Q", f.read(8))
        elems = 1
        for d in dims:
            elems *= d
        try:
            blk, tsz = GGML_QUANT_SIZES[ttype]
            nbytes = elems * tsz // blk
        except KeyError:
            nbytes = -1
        end = offset + (nbytes if nbytes > 0 else 0)
        max_end = max(max_end, end)
        if nbytes < 0 or end > fsize:
            bad.append((name, ttype, dims, offset, nbytes, end))

print(f"期望数据区终点: {max_end:,} ({max_end/1024**3:.3f} GiB)")
delta = max_end - fsize
if delta > 0:
    print(f"❌ 数据区终点超文件 {delta:,} bytes —— 文件不完整/数据缺失")
elif delta == 0:
    print("✅ 数据区终点 == 文件大小，文件完整")
else:
    print(f"⚠️ 终点比文件小 {-delta:,} bytes")
print(f"越界/未知类型 tensor: {len(bad)}")
for b in bad[:6]:
    print("  ", b)
