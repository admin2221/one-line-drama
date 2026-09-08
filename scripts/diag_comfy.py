# -*- coding: utf-8 -*-
"""诊断：ComfyUI 健康 + 队列 + 僵尸任务检查。可选 --interrupt 清理。"""
import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")


def req(method, path, data=None):
    r = urllib.request.Request("http://127.0.0.1:8188" + path, data=data, method=method)
    with urllib.request.urlopen(r, timeout=30) as resp:
        b = resp.read()
        try:
            return json.loads(b.decode())
        except Exception:
            return b


try:
    ss = req("GET", "/system_stats")
    dev = ss.get("devices", [{}])[0] if ss.get("devices") else {}
    print("ComfyUI ONLINE | vram_total:", dev.get("vram_total"),
          "| vram_free:", dev.get("vram_free"))
except Exception as e:
    print("ComfyUI OFFLINE/ERR:", e)
    sys.exit(1)

q = req("GET", "/queue")
run = q.get("queue_running", [])
pend = q.get("queue_pending", [])
print("queue running:", len(run), "pending:", len(pend))
for item in run:
    print("  RUNNING prompt_id:", item[1])
for item in pend:
    print("  PENDING prompt_id:", item[1])

if "--interrupt" in sys.argv:
    req("POST", "/interrupt")
    print("sent /interrupt")
