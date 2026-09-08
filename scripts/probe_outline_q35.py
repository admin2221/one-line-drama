# -*- coding: utf-8 -*-
"""用 qwen3.5 提交总纲探针，验证是否干净输出不思考。"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\Comfyui\comfyui-drama")
from factory.client import ComfyClient
import factory.generator as g
from factory.drama_factory import parse_json_block

STORY = ("深夜老书店即将拆迁，店主沈唐收到一本能照见亡者的旧日记；"
         "神秘女读者叶澜在书页夹缝发现真相，警探宋远追查一系列城市失踪案，"
         "三人于最后一夜在书店对峙，解开二十年前的旧案。")

client = ComfyClient(base_url="http://127.0.0.1:8188")
api = g.build_outline_prompt(STORY, 165, 41, 10, llm="qwen3.5", n_char=3)
pid = client.queue_prompt(api)["prompt_id"]
print("submitted pid:", pid, flush=True)
entry = client.wait_done(pid)
lines = ["status: " + str(entry.get("status", {}).get("status_str"))]
text = client.first_text(entry)
lines.append("text len: " + str(len(text) or 0))
obj = parse_json_block(text)
if obj:
    lines.append("PARSE-OK characters:%d scenes:%d props:%d beats:%d" % (
        len(obj.get("characters", [])), len(obj.get("scenes", {})),
        len(obj.get("props", {})), len(obj.get("beats", []))))
    chars = obj.get("characters", [])
    if chars:
        lines.append("char names: " + ", ".join(c.get("name", "") for c in chars))
else:
    lines.append("PARSE-FAIL. head: " + text[:150].replace("\n", " "))
    lines.append("has beats: " + str('"beats"' in text))
report = "\n".join(lines)
print(report, flush=True)
with open(r"D:\Comfyui\comfyui-drama\probe_q35_out.txt", "w", encoding="utf-8") as f:
    f.write(report)
