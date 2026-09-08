# -*- coding: utf-8 -*-
"""诊断 parse_json_block 失败原因。"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
with open(r"D:\Comfyui\comfyui-drama\scripts\outline_min_out.txt", encoding="utf-8") as f:
    text = f.read()

start = text.find("{")
end = text.rfind("}")
print("first { at:", start, " last } at:", end, " len:", len(text))
cand = text[start:end + 1]
print("candidate len:", len(cand))
print("candidate head 120:", repr(cand[:120]))
print("candidate tail 120:", repr(cand[-120:]))
try:
    obj = json.loads(cand)
    print("PARSED OK:", obj.get("title"))
except Exception as e:
    print("parse err:", e)
    # 找错误位置
    dec = json.JSONDecoder()
    try:
        idx = 0
        obj, idx = dec.raw_decode(cand)
        print("partial ok up to", idx, "then:", repr(cand[idx:idx + 100]))
    except Exception as e2:
        print("raw_decode err:", e2)
        # 逐字符定位
        for i in range(len(cand)):
            try:
                json.loads(cand[:i+1])
            except Exception:
                pass
