# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
import inspect
import llama_cpp

print("version:", getattr(llama_cpp, "__version__", "?"))
params = inspect.signature(llama_cpp.Llama.__init__).parameters
names = list(params)
print("has draft_model:", "draft_model" in names)
kw = [k for k in names if "draft" in k.lower() or "mtp" in k.lower()
      or "spec" in k.lower() or "lookahead" in k.lower() or "backtrack" in k.lower()]
print("speculative-ish kwargs:", kw)
d = params.get("draft_model")
if d is not None:
    print("draft_model default:", d.default)
d2 = params.get("draft_parallel_tokens")
if d2 is not None:
    print("draft_parallel_tokens default:", d2.default)
