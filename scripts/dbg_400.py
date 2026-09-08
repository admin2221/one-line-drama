# -*- coding: utf-8 -*-
"""调试 400 响应体：分别测 n_ctx=16384 / max_tokens=16000 是否被拒绝。"""
import json, sys, urllib.request, urllib.error
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\Comfyui\comfyui-drama")
from factory import generator
from factory.prompts import SCRIPT_DIRECTOR_PROMPT

STORY = "一个落魄书生在雨夜捡到一枚能穿越时空的古镜，他回到过去改变了命运，却发现镜中自己的脸越来越模糊。"

def try_queue(api, label):
    body = json.dumps({"prompt": api, "client_id": "dbg"}).encode()
    req = urllib.request.Request("http://127.0.0.1:8188/prompt", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            print(f"{label}: OK {r.read().decode()[:200]}")
    except urllib.error.HTTPError as e:
        print(f"{label}: HTTP {e.code}")
        print("  body:", e.read().decode()[:800])

system = SCRIPT_DIRECTOR_PROMPT + "\n\n【目标时长】约45镜头，总时长接近180秒，宁可单镜头稍长也不要删减剧情。"

# 测试1: 默认 4096/8192
try_queue(generator.build_script_prompt(STORY, system), "默认 4096/8192")
# 测试2: 大 max_tokens + 大 n_ctx
try_queue(generator.build_script_prompt(STORY, system, max_tokens=16000, n_ctx=16384), "16000/16384")
# 测试3: 大 max_tokens + 默认 n_ctx
try_queue(generator.build_script_prompt(STORY, system, max_tokens=16000, n_ctx=8192), "16000/8192")
# 测试4: 仅加大 max_tokens=8192, n_ctx=8192
try_queue(generator.build_script_prompt(STORY, system, max_tokens=8192, n_ctx=8192), "8192/8192")
