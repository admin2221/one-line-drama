# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
import glob, os
MODEL = r"D:\Comfyui\Comfyui\models\LLM\Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-IQ3_M.gguf"

try:
    from gguf import GGUFReader
except Exception as e:
    print("no gguf lib:", e); sys.exit(0)

r = GGUFReader(MODEL)
names = [t.name for t in r.tensors]
mtp = [n for n in names if "mtp" in n.lower() or "draft" in n.lower() or "_ms" in n.lower()]
print("total tensors:", len(names))
print("MTP/draft-ish tensors:", mtp if mtp else "无（模型不含 MTP 模块权重）")
print("sample:", names[:5], "...", names[-3:])
