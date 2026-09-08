# -*- coding: utf-8 -*-
import sys, json, urllib.request, urllib.error
sys.stdout.reconfigure(encoding="utf-8")
KEY = "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"

def probe(path, payload):
    url = "https://ai.api.nvidia.com" + path
    headers = {"Authorization": "Bearer "+KEY, "Content-Type":"application/json","Accept":"application/json"}
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, r.read().decode("utf-8","replace")[:300]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8","replace")[:300]
    except Exception as e:
        return 0, str(e)[:150]

# 用最小 base64 图片(1x1 png) + 驱动视频占位。检测端点存活：404=不存在, 400/422=存在但参数错
tiny_png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
payload = {"prompt":"test", "image":tiny_png, "video":"data:video/mp4;base64,", "seed":0}

paths = [
  "/v1/genai/wan-ai/wan2.2-animate-2-14b",
  "/v1/video/wan-ai/wan2.2-animate-2-14b",
  "/v1/genai/wan-ai/wan2.2-animate-2-14b/infer",
]
for p in paths:
    st, body = probe(p, payload)
    flag = "LIVE" if st not in (404,) else "404"
    print(f"{p}  -> {st} [{flag}] | {body.replace(chr(10),' ')[:120]}")
