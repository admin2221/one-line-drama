# -*- coding: utf-8 -*-
"""分析 llm_outline_raw 失败原因 + 测试提取。"""
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\Comfyui\comfyui-drama")
from factory.drama_factory import parse_json_block

with open(r"D:\Comfyui\comfyui-drama\output\drama_wusu_3min\llm_outline_raw.txt", encoding="utf-8") as f:
    text = f.read()
obj = parse_json_block(text)
print("parse:", "OK" if obj else "FAIL", "| len:", len(text))
if obj:
    print("keys:", list(obj.keys()))
    print("characters:", len(obj.get("characters", [])), [c.get("name") for c in obj.get("characters", [])] if obj.get("characters") else "-")
    print("beats:", len(obj.get("beats", [])))
else:
    print("has think:", "<think>" in text)
    print("has brackets:", text.count("{"), text.count("}"))
    print("head:", text[:300])
