# -*- coding: utf-8 -*-
import struct, sys, os
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\Comfyui\Comfyui\custom_nodes\ComfyUI-llama-cpp_vlm\support")
import gguf_layers as gl

path = r"D:\Comfyui\Comfyui\models\LLM\Qwen3.8-27B-UD-Q4_K_S.gguf"
with open(path, "rb") as f:
    head = f.read(24)
    version, n_tensors, n_kv = struct.unpack("<IQQ", head[4:24])
    for i in range(n_kv):
        key = gl.read_string(f)
        gl.read_value(f)
    off = f.tell()
    print("kv 解析结束偏移:", off)
    f.seek(off)
    b = f.read(32)
    print("此处 32 字节:", b.hex())
    if b[:8] == b"\x00" * 8:
        print("⚠️ 位置全零——kv 解析可能多读/少读")
    ln = struct.unpack("<Q", b[:8])[0]
    print("解读为 u64 length =", ln)
    print("下一个 u64 偏移 +8 =", struct.unpack("<Q", b[8:16])[0])
