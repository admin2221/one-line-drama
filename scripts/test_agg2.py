# -*- coding: utf-8 -*-
"""Aggressive 模型 - 短剧本端到端验证（n_ctx=8192/vram_limit=12）。
验证剧本推理+扩写、JSON 含 duration 8-15 / plot / dialogue / transition_prev。
带超时中断机制。
"""
import sys, time, os, json, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\Comfyui\comfyui-drama")
from factory import generator
from factory.client import ComfyClient
from factory.drama_factory import parse_json_block
from factory.prompts import SCRIPT_DIRECTOR_PROMPT

BASE = "http://127.0.0.1:8188"
TIMEOUT = 600
POLL = 8
client = ComfyClient(BASE)

story = "雨夜落魄书生捡到古镜，镜中女子穿越而来，两人忘情相爱，却被命运强行拆散"
api = generator.build_script_prompt(story, SCRIPT_DIRECTOR_PROMPT,
                                    max_tokens=6500, llm="qwen3.8ag")
pid = client.queue_prompt(api)["prompt_id"]
print("LLM=qwen3.8ag 提交剧本任务，prompt_id:", pid, flush=True)
t0 = time.time()
ok = False
while time.time() - t0 < TIMEOUT:
    time.sleep(POLL)
    try:
        h = json.load(urllib.request.urlopen(BASE + "/history/" + pid, timeout=8))
    except Exception:
        h = {}
    rec = h.get(pid)
    if rec:
        st = rec.get("status", {})
        if st.get("status_str") == "error":
            print(f"耗时{time.time()-t0:.0f}s → error"); print(str(st.get("messages"))[:400]); sys.exit(2)
        if st.get("completed"):
            text = client.first_text(rec)
            print(f"耗时{time.time()-t0:.0f}s → 完成, 返回长度 {len(text or '')}", flush=True)
            ok = True
            break
    if int(time.time() - t0) % 40 < POLL:
        print(f"  [{time.time()-t0:.0f}s] 推理中…", flush=True)
        try:
            d = json.load(urllib.request.urlopen(BASE + "/system_stats", timeout=8))
            print("    GPU used MB:", d.get("devices", [{}])[0].get("vram_used", 0)//1024//1024, flush=True)
        except Exception:
            pass

if not ok:
    print(f"❌ 超过 {TIMEOUT}s 未完成，中断。")
    try: urllib.request.urlopen(BASE + "/interrupt", timeout=5)
    except Exception: pass
    sys.exit(3)

raw = os.path.join(r"D:\Comfyui\comfyui-drama\output", "_agg_raw2.txt")
with open(raw, "w", encoding="utf-8") as f:
    f.write(text or "")

script = parse_json_block(text)
if not script or "shots" not in script:
    print("❌ JSON 解析失败，原文存", raw)
    print("前600字:", (text or "")[:600]); sys.exit(1)

shots = script["shots"]
print("✅ 剧本：《%s》 %d 镜头" % (script.get("title", "?"), len(shots)))
du = [float(str(s.get("duration", "0")).strip() or 0) for s in shots]
print("   duration:", du, "→ 全在8-15:", all(8 <= x <= 15 for x in du))
print("   缺 plot:", [s.get("shot") for s in shots if not s.get("plot")] or "无",
      "| 缺对话:", [s.get("shot") for s in shots if not s.get("dialogue")] or "无",
      "| 缺衔接:", [s.get("shot") for s in shots if not s.get("transition_prev")] or "无")
for s in shots[:2]:
    print(f"   shot{s.get('shot')} [{s.get('duration')}s] {s.get('scene')}")
    print("       plot:", (s.get("plot") or "")[:80])
    print("       dialogue:", (s.get("dialogue") or "")[:60])
print("AGG_SCRIPT_OK")
