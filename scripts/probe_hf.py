# -*- coding: utf-8 -*-
"""探测 HF 源文件：Content-Length 与 Range 支持。"""
import sys
import urllib.request
import urllib.error

sys.stdout.reconfigure(encoding="utf-8")
URL = "https://huggingface.co/unsloth/Qwen3.8-27B-UD-GGUF/resolve/main/Qwen3.8-27B-UD-Q4_K_S.gguf"

for label, url, headers in [
    ("HEAD", URL, {}),
    ("Range最后8字节", URL, {"Range": "bytes=-8"}),
]:
    req = urllib.request.Request(url, method="GET" if label != "HEAD" else "HEAD")
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"[{label}] status={r.status}")
            print("   Content-Length:", r.headers.get("Content-Length"))
            print("   Content-Range:", r.headers.get("Content-Range"))
            print("   Accept-Ranges:", r.headers.get("Accept-Ranges"))
            data = r.read(64)
            if data:
                print("   返回前64字节:", data[:16].hex())
    except urllib.error.HTTPError as e:
        print(f"[{label}] HTTP {e.code}: {e.reason}")
        print("   Content-Length:", e.headers.get("Content-Length"))
        print("   Content-Range:", e.headers.get("Content-Range"))
        print("   Accept-Ranges:", e.headers.get("Accept-Ranges"))
    except Exception as e:
        print(f"[{label}] ❌ {type(e).__name__}: {e}")
