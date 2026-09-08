# -*- coding: utf-8 -*-
"""等待 ComfyUI 就绪并验证健康检查。"""
import sys, time, urllib.request
sys.stdout.reconfigure(encoding="utf-8")

deadline = time.time() + 180
ok = None
while time.time() < deadline:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=3) as r:
            ok = r.read().decode()
            break
    except Exception:
        time.sleep(5)
if not ok:
    print("ComfyUI 未在 180s 内就绪")
    sys.exit(1)
import json
d = json.loads(ok)
print("就绪！version:", d.get("system", {}).get("comfyui_version"))
dev = d.get("devices", [{}])[0]
print("GPU:", dev.get("name"), "| VRAM:", dev.get("vram_total", 0) // (1024**3), "GB")
