# -*- coding: utf-8 -*-
"""探测候选 URL（含镜像）。"""
import sys
import urllib.request
import urllib.error

sys.stdout.reconfigure(encoding="utf-8")
CANDIDATES = [
    "https://huggingface.co/unsloth/Qwen3.8-27B-GGUF/resolve/main/Qwen3.8-27B-UD-Q4_K_S.gguf",
    "https://huggingface.co/unsloth/Qwen3.8-27B-UD-GGUF/resolve/main/Qwen3.8-27B-UD-Q4_K_S.gguf",
    "https://hf-mirror.com/unsloth/Qwen3.8-27B-GGUF/resolve/main/Qwen3.8-27B-UD-Q4_K_S.gguf",
    "https://hf-mirror.com/unsloth/Qwen3.8-27B-UD-GGUF/resolve/main/Qwen3.8-27B-UD-Q4_K_S.gguf",
]
for url in CANDIDATES:
    req = urllib.request.Request(url, method="HEAD")
    req.add_header("Range", "bytes=-8")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"✅ {url}")
            print(f"   status={r.status} len={r.headers.get('Content-Length')} range={r.headers.get('Content-Range')}")
    except urllib.error.HTTPError as e:
        print(f"❌ {url}  ->  HTTP {e.code}")
    except Exception as e:
        print(f"❌ {url}  ->  {type(e).__name__}: {e}")
