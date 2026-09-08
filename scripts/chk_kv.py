# -*- coding: utf-8 -*-
import struct, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\Comfyui\Comfyui\custom_nodes\ComfyUI-llama-cpp_vlm\support")
import gguf_layers as gl

path = r"D:\Comfyui\Comfyui\models\LLM\Qwen3.8-27B-UD-Q4_K_S.gguf"
with open(path, "rb") as f:
    head = f.read(24)
    version, n_tensors, n_kv = struct.unpack("<IQQ", head[4:24])
    for i in range(n_kv):
        start = f.tell()
        try:
            key = gl.read_string(f)
            val = gl.read_value(f)
            print(f"kv{i:02d} @{start:,} key={key[:40]!r} ok  now@{f.tell():,}")
        except Exception as e:
            print(f"kv{i:02d} @{start:,} ❌ {type(e).__name__}: {e}")
            break
    off = f.tell()
    print("最终偏移:", off)
    f.seek(off)
    b = f.read(16)
    print("此处 16 字节:", b.hex())
