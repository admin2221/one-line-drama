# -*- coding: utf-8 -*-
"""Extract both system prompts verbatim into factory/prompts/*.txt."""
import json
import os
import sys
sys.stdout.reconfigure(encoding="utf-8")

OUT = r"D:\Comfyui\comfyui-drama\factory\prompts"
os.makedirs(OUT, exist_ok=True)

# 1) imageai visual-concept designer system_prompt
wf = json.load(open(r"D:\Comfyui\Comfyui\user\default\workflows\imageai.json", encoding="utf-8"))
for n in wf["nodes"]:
    if n["type"] == "llama_cpp_instruct_adv":
        wv = n.get("widgets_values", [])
        sp = wv[2]
        with open(os.path.join(OUT, "image_enhancer.txt"), "w", encoding="utf-8") as f:
            f.write(sp)
        print("image_enhancer.txt:", len(sp), "chars")
        break

# 2) 20-shot script director system_prompt (verbatim, for reference)
wf = json.load(open(r"D:\Comfyui\Comfyui\user\default\workflows\一句话短剧20镜头.json", encoding="utf-8"))
for n in wf["nodes"]:
    if n["type"] == "llama_cpp_instruct_adv":
        wv = n.get("widgets_values", [])
        sp = wv[2]
        with open(os.path.join(OUT, "script_director_20shot.txt"), "w", encoding="utf-8") as f:
            f.write(sp)
        print("script_director_20shot.txt:", len(sp), "chars")
        break
