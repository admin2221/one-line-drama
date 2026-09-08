# -*- coding: utf-8 -*-
"""断点续传下载 wheel，直到完整。"""
import os
import sys
import time
import urllib.request
import urllib.error

sys.stdout.reconfigure(encoding="utf-8")
TAG = "v0.3.48-cu130-win-20260821"
NAME = "llama_cpp_python-0.3.48+cu130-cp312-cp312-win_amd64.whl"
URL = f"https://github.com/JamePeng/llama-cpp-python/releases/download/{TAG}/{NAME}"
DST = rf"D:\Comfyui\wheels\{NAME}"


def total_size():
    req = urllib.request.Request(URL, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return int(r.headers.get("Content-Length", 0))


def resume(dst, expect):
    have = os.path.getsize(dst) if os.path.exists(dst) else 0
    if have >= expect:
        return True, have
    print(f"已有 {have:,} / {expect:,}，从 {have:,} 续传…")
    while have < expect:
        headers = {"User-Agent": "Mozilla/5.0", "Range": f"bytes={have}-"}
        req = urllib.request.Request(URL, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                with open(dst, "ab") as f:
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        f.write(chunk)
                        have += len(chunk)
                        print(f"\r  {have/1024**2:.0f}/{expect/1024**2:.0f} MiB ({100*have/expect:.0f}%)", end="")
        except Exception as e:
            print(f"\n连接中断({type(e).__name__})，3s 后重试…")
            time.sleep(3)
    print()
    return True, have


expect = total_size()
print("服务器总大小:", expect, "bytes")
ok, have = resume(DST, expect)
print("下载完成:", DST, f"{have:,} bytes")
print("SHA256:", end=" ")
import hashlib
h = hashlib.sha256()
with open(DST, "rb") as f:
    while True:
        b = f.read(1 << 20)
        if not b:
            break
        h.update(b)
print(h.hexdigest())
