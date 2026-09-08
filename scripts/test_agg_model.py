# -*- coding: utf-8 -*-
"""用 Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-IQ3_M.gguf 通过 ComfyUI 跑一次短剧本，
验证：模型能加载、能进行剧本推理与扩写、输出 JSON 含 duration 8-15 / plot / dialogue / transition_prev。
"""
import json
import os
import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\Comfyui\comfyui-drama")

from factory import generator
from factory.client import ComfyClient
from factory.drama_factory import run_and_get_text, parse_json_block
from factory.prompts import SCRIPT_DIRECTOR_PROMPT

BASE = "http://127.0.0.1:8188"
client = ComfyClient(BASE)
story = "雨夜落魄书生捡到古镜，镜中女子穿越而来，两人忘情相爱，却又被命运强行拆散"

print("LLM key = qwen3.8ag")
print("config =", generator.LLM_CONFIGS["qwen3.8ag"])
print("=" * 55)
print("提交 LLM 剧本任务（加载 27B Aggressive 模型，首次加载较慢）…")

# 短剧本用 build_script_prompt；加大 max_tokens
api = generator.build_script_prompt(story, SCRIPT_DIRECTOR_PROMPT,
                                    max_tokens=12000, llm="qwen3.8ag")
text = run_and_get_text(client, api)

print("LLM 返回长度:", len(text or ""))
raw = os.path.join(r"D:\Comfyui\comfyui-drama\output", "_agg_raw.txt")
with open(raw, "w", encoding="utf-8") as f:
    f.write(text or "")

script = parse_json_block(text)
if not script or "shots" not in script:
    print("❌ 剧本 JSON 解析失败，原文已存", raw)
    print("原文前800字：", (text or "")[:800])
    sys.exit(1)

shots = script["shots"]
print("✅ 剧本生成成功：《%s》 %d 镜头" % (script.get("title", "?"), len(shots)))
du = [float(str(s.get("duration", "0")).strip() or 0) for s in shots]
print("   duration:", du, "→ 全在 8-15:", all(8 <= x <= 15 for x in du) if du else "无")
miss_plot = [s.get("shot") for s in shots if not s.get("plot")]
miss_dg = [s.get("shot") for s in shots if not s.get("dialogue")]
miss_tr = [s.get("shot") for s in shots if not s.get("transition_prev")]
print("   缺 plot:", miss_plot or "无", "| 缺 dialogue:", miss_dg or "无", "| 缺 transition_prev:", miss_tr or "无")
print("   character:", script.get("character", "")[:60])
print("   style:", script.get("style", "")[:40])
for s in shots[:2]:
    print(f"\n   shot{s.get('shot')} [{s.get('duration')}s] {s.get('scene')}")
    print("      plot:", (s.get("plot") or ""))
    print("      dialogue:", (s.get("dialogue") or ""))
    print("      transition_prev:", (s.get("transition_prev") or "")[:60])
print("\nAGG_MODEL_TEST_OK")
