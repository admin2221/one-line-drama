# -*- coding: utf-8 -*-
"""打印 parse_json_block 提取到的对象与真实最后一个 JSON。"""
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\Comfyui\comfyui-drama")
from factory.drama_factory import parse_json_block

with open(r"D:\Comfyui\comfyui-drama\output\drama_3char_3min\llm_outline_raw.txt", encoding="utf-8") as f:
    text = f.read()

obj = parse_json_block(text)
print("EXTRACTED:", json.dumps(obj, ensure_ascii=False)[:300] if obj else "None")

# 手动：找到最大完整的 JSON 对象（从后往前找含 "beats" 的）
def scan_objects(s):
    objs = []
    stack = []
    in_str = False
    esc = False
    for i, c in enumerate(s):
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "{":
                stack.append(i)
            elif c == "}":
                if stack:
                    objs.append((stack.pop(), i))
    return objs

for s, e in reversed(scan_objects(text)):
    cand = text[s:e + 1]
    if '"beats"' in cand:
        print("LARGEST-with-beats len:", e - s)
        try:
            o = json.loads(cand)
            print("PARSE-OK beats:", len(o.get("beats", [])), "chars:", len(o.get("characters", [])))
        except Exception as ex:
            print("PARSE-FAIL:", str(ex)[:200])
            # 定位未转义引号问题
            print("cand tail:", cand[-400:])
        break
