# -*- coding: utf-8 -*-
"""解析 17 幕总纲 JSON 并打印结构摘要。"""
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\Comfyui\comfyui-drama")
from factory.drama_factory import parse_json_block

with open(r"D:\Comfyui\comfyui-drama\scripts\outline17.txt", encoding="utf-8") as f:
    text = f.read()

obj = parse_json_block(text)
if not obj:
    print("解析失败")
    sys.exit(1)
print("title:", obj.get("title"))
print("beats:", len(obj.get("beats", [])))
for i, b in enumerate(obj.get("beats", []), 1):
    print(f"  {i:>2}. {b.get('scene')} | {b.get('brief', '')[:50]}...")
print("character:", obj.get("character", ""))
print("style:", obj.get("style", ""))
