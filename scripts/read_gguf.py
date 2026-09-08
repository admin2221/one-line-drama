# -*- coding: utf-8 -*-
"""读取 GGUF 头部（v3 类型表），获取架构与 chat 模板。"""
import struct
import sys

sys.stdout.reconfigure(encoding="utf-8")

path = r"D:\Comfyui\Comfyui\models\LLM\Qwen3.8-27B-UD-Q4_K_S.gguf"

FMT = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f", 7: "<?", 8: None,
       9: "<Q", 10: "<q", 11: "<d"}

with open(path, "rb") as f:
    head = f.read(24)
    assert head[:4] == b"GGUF"
    version, n_tensors, n_kv = struct.unpack("<IQQ", head[4:24])
    print(f"GGUF v{version} tensors={n_tensors} kv={n_kv}")

    def read_str():
        ln, = struct.unpack("<Q", f.read(8))
        return f.read(ln).decode("utf-8", "replace")

    def read_scalar(t):
        if t == 8:
            return read_str()
        return struct.unpack(FMT[t], f.read(struct.calcsize(FMT[t])))[0]

    for _ in range(n_kv):
        key = read_str()
        typ = struct.unpack("<I", f.read(4))[0]
        if typ & 0x80000000:  # array
            base = typ & 0x7FFFFFFF
            arr_len, = struct.unpack("<Q", f.read(8))
            vals = [read_scalar(base) for _ in range(arr_len)]
            val = f"[{', '.join(str(v)[:60] for v in vals[:8])}{'...' if arr_len > 8 else ''}]"
        else:
            val = read_scalar(typ)
        if key in ("tokenizer.chat_template", "general.name"):
            val = str(val)[:600]
        if key in ("general.architecture", "general.name", "general.file_type",
                   "qwen3.chat_template", "tokenizer.chat_template",
                   "general.context_length", "general.rope_scaling.type",
                   "llama.vocab_size", "qwen3.block_count", "qwen3.attention.head_count_kv"):
            print(f"{key}: {val}")
