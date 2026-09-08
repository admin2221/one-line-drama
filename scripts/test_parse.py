# -*- coding: utf-8 -*-
"""测试 parse_json_block 能否从 llm_outline_raw 提取 JSON。"""
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\Comfyui\comfyui-drama")
from factory.drama_factory import parse_json_block

with open(r"D:\Comfyui\comfyui-drama\output\drama_3char_3min\llm_outline_raw.txt", encoding="utf-8") as f:
    text = f.read()
obj = parse_json_block(text)
print("RESULT:", "OK" if obj else "FAIL")
if obj:
    print("title:", obj.get("title"))
    print("characters:", len(obj.get("characters", [])))
    print("scenes:", len(obj.get("scenes", {})))
    print("props:", len(obj.get("props", {})))
    print("beats:", len(obj.get("beats", [])))
else:
    # 找最后一个 JSON 对象
    import json, re
    # 统计花括号
    print("brace count:", text.count("{"), text.count("}"))
    # 看最后2000字符
    print("=== TAIL ===")
    print(text[-1500:])
