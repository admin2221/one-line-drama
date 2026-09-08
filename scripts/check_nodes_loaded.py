# -*- coding: utf-8 -*-
"""验证运行中的 ComfyUI 已加载新节点定义（max_tokens 上限解除）。"""
import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

with urllib.request.urlopen("http://127.0.0.1:8188/object_info/llama_cpp_parameters") as r:
    d = json.load(r)
node = d["llama_cpp_parameters"]
inp = node["input"]["required"]
opt = node["input"].get("optional", {})
print("required keys:", sorted(inp.keys()))
mt = inp["max_tokens"]
print("max_tokens:", mt)
mt_max = mt[1]["max"]
print("RESULT:", "OK 262144" if mt_max >= 262144 else f"FAIL {mt_max}")
