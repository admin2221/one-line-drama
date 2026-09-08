# -*- coding: utf-8 -*-
"""极短探针：验证 qwen3.8ag 在 n_ctx=8192 / vram_limit=12 下能否出文本。
带超时：超过 TIMEOUT 秒仍未出结果则中断并报告。
"""
import sys, time, json, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\Comfyui\comfyui-drama")
from factory import generator
from factory.client import ComfyClient

BASE = "http://127.0.0.1:8188"
TIMEOUT = 240   # 秒；若模型能跑，极短问答应在模型加载后几十秒内出
POLL = 6

client = ComfyClient(BASE)

print("config n_ctx=%s vram_limit=%s" % (generator.LLM_CONFIGS["qwen3.8ag"]["n_ctx"],
                                          generator.LLM_CONFIGS["qwen3.8ag"]["vram_limit"]))
# 极短 prompt（<20 字），避开长输出
api = generator.build_script_prompt("请只回复两个字：正常。", "助手，必须极其简短地回答。",
                                    max_tokens=64, llm="qwen3.8ag")
pid = client.queue_prompt(api)["prompt_id"]
print("已提交 prompt_id:", pid, "开始加载+推理（首次加载较慢）…")
t0 = time.time()

ok = False
while time.time() - t0 < TIMEOUT:
    time.sleep(POLL)
    # 任务是否完成？
    try:
        h = json.load(urllib.request.urlopen(BASE + "/history/" + pid, timeout=8))
    except Exception:
        h = {}
    rec = h.get(pid)
    if rec:
        st = rec.get("status", {})
        if st.get("status_str") == "error":
            print(f"耗时{time.time()-t0:.0f}s → 任务 error")
            print("  ", str(st.get("messages"))[:400]); sys.exit(2)
        if st.get("completed"):
            txt = client.first_text(rec)
            print(f"耗时{time.time()-t0:.0f}s → 完成")
            print("返回文本 repr:", repr(txt)[:500])
            ok = True
            break
    # 中途每秒打印一次显存/队列状态（最多打印几次，避免刷屏）
    if int(time.time() - t0) % (POLL * 4) < 2:
        print(f"  [{time.time()-t0:.0f}s] 仍运行中…", flush=True)

if not ok:
    print(f"❌ 超过 {TIMEOUT}s 未出文本，主动中断。")
    try:
        urllib.request.urlopen(BASE + "/interrupt", timeout=5)
    except Exception:
        pass
    # 打印当前 GPU 用量辅助判断
    d = json.load(urllib.request.urlopen(BASE + "/system_stats", timeout=8))
    for dev in d.get("devices", []):
        print("  GPU used MB:", dev.get("vram_used", 0)//1024//1024)
    sys.exit(3)
print("PROBE_OK")
