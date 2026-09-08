# -*- coding: utf-8 -*-
"""Extract LLM director system_prompt + key widgets from the 20-shot workflow."""
import json
import sys
sys.stdout.reconfigure(encoding="utf-8")

wf = json.load(open(r"D:\Comfyui\Comfyui\user\default\workflows\一句话短剧20镜头.json", encoding="utf-8"))
for n in wf["nodes"]:
    if n["type"] == "llama_cpp_instruct_adv":
        print("NODE", n["id"], n.get("title"))
        wv = n.get("widgets_values", [])
        print("=== widgets_values ===")
        print(json.dumps(wv, ensure_ascii=False, indent=1))
        print("=== system_prompt (index 2) ===")
        print(wv[2])
        break
