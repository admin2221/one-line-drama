# -*- coding: utf-8 -*-
"""查看 h3hbai.json 画布格式中 MiniMaxH3ReferenceToVideo 节点的完整 inputs 结构。"""
import json
import sys
sys.stdout.reconfigure(encoding="utf-8")

wf = json.load(open(r"D:\Comfyui\Comfyui\user\default\workflows\h3hbai.json", encoding="utf-8"))
for n in wf["nodes"]:
    if n["type"] == "MiniMaxH3ReferenceToVideo":
        print("NODE", n["id"], n.get("title"))
        print("widgets_values:", n.get("widgets_values"))
        print("=== inputs ===")
        print(json.dumps(n.get("inputs", []), ensure_ascii=False, indent=1))
        print("=== outputs ===")
        print(json.dumps(n.get("outputs", []), ensure_ascii=False, indent=1))
        break
