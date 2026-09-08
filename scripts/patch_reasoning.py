# -*- coding: utf-8 -*-
"""在 llama_cpp_parameters 节点加 reasoning_budget 参数（幂等）。"""
import io
import sys

sys.stdout.reconfigure(encoding="utf-8")
path = r"D:\Comfyui\Comfyui\custom_nodes\ComfyUI-llama-cpp_vlm\nodes.py"

with open(path, "r", encoding="utf-8") as f:
    text = f.read()

OLD = '"mirostat_tau": ("FLOAT", {"default": 5.0, "min": 0.0, "max": 10.0, "step": 0.01}),\n                "state_uid": ("INT", {'
NEW = ('"mirostat_tau": ("FLOAT", {"default": 5.0, "min": 0.0, "max": 10.0, "step": 0.01}),\n'
       '                "reasoning_budget": ("INT", {\n'
       '                    "default": 0, "min": -1, "max": 1000000, "step": 1,\n'
       '                    "tooltip": "Max tokens for <think> reasoning block (0 = disable thinking, -1 = unlimited)"\n'
       '                }),\n'
       '                "state_uid": ("INT", {')

if "reasoning_budget" in text:
    print("already present, skip")
elif OLD in text:
    text = text.replace(OLD, NEW)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print("patched OK")
else:
    print("OLD pattern not found! lines around 'state_uid':")
    idx = text.find("state_uid")
    print(repr(text[idx - 400:idx + 200]))
