# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
import inspect
import llama_cpp

params = inspect.signature(llama_cpp.Llama.__init__).parameters
for k in ["load_mtp", "draft_model", "speculative", "draft_parallel_tokens", "lookahead", "model_kwargs", "mtp_gguf", "mtp_seq", "n_draft_cache", "backtrack"]:
    p = params.get(k)
    if p is not None:
        print(f"{k}: default={p.default!r}")
print("\n--- Llama init full signature (param -> default) ---")
for name, p in params.items():
    if name in ("verbose", "n_gpu_layers", "n_ctx", "model_path", "chat_handler"):
        continue
    print(f"  {name} = {p.default!r}")
