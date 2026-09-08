# -*- coding: utf-8 -*-
"""提取 20镜头工作流中 duration 相关节点的精确 widgets，供工作流生成器复用。"""
import json
import sys
sys.stdout.reconfigure(encoding="utf-8")

wf = json.load(open(r"D:\Comfyui\Comfyui\user\default\workflows\一句话短剧20镜头.json", encoding="utf-8"))
by_id = {n["id"]: n for n in wf["nodes"]}
for nid in (305, 306, 314, 313):
    n = by_id.get(nid)
    if n:
        print(f"[{nid}] {n['type']} '{n.get('title')}'")
        print("  widgets_values:", json.dumps(n.get("widgets_values"), ensure_ascii=False))
        print("  inputs:", json.dumps(n.get("inputs"), ensure_ascii=False))
        print()
