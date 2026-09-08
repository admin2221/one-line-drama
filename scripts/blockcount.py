# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
from gguf import GGUFReader
MODEL = r"D:\Comfyui\Comfyui\models\LLM\Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-IQ3_M.gguf"
r = GGUFReader(MODEL)
print("fields ending .block_count:")
for k, f in r.fields.items():
    if k.endswith(".block_count"):
        try:
            val = f.contents
            print("  ", k, "=", val)
        except Exception as e:
            print("  ", k, "read err", e)
# 也读主 llama.block_count 字段（GGUFReader API）
for wanted in ("llama.block_count", "qwen3m.block_count", "general.architecture"):
    try:
        f = r.get_field(wanted)
        print(wanted, "=", f.contents if f else None)
    except Exception as e:
        print(wanted, "err", e)
