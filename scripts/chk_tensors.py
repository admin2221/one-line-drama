# -*- coding: utf-8 -*-
import struct, sys, os
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
        start = f.tell()
        try:
            name = gl.read_string(f)
            n_dims, = struct.unpack("<I", f.read(4))
            dims = list(struct.unpack(f"<{n_dims}Q", f.read(8 * n_dims)))
            ttype, = struct.unpack("<I", f.read(4))
            if i % 100 == 0 or i > 850:
                print(f"t{i:04d} @{start:,} name={name[:40]!r} dims={dims} type={ttype}")
        except Exception as e:
            print(f"t{i:04d} @{start:,} ❌ {type(e).__name__}: {e}")
            f.seek(start)
            print("  bytes@start:", f.read(24).hex())
            break
    print("info 解析结束:", f.tell())
