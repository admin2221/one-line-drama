# -*- coding: utf-8 -*-
import json, sys, urllib.request
sys.stdout.reconfigure(encoding="utf-8")

def get(path):
    with urllib.request.urlopen("http://127.0.0.1:8188" + path, timeout=15) as r:
        return json.load(r)

# 检查 llama_cpp_model_loader 的 MTP 相关参数
try:
    info = get("/object_info/llama_cpp_model_loader")
    n = info["llama_cpp_model_loader"]
    print("=== llama_cpp_model_loader 输入 ===")
    for group, fields in n.get("input", {}).items():
        for k, v in fields.items():
            print(f"  [{group}] {k}: {v}")
except Exception as e:
    print("loader err:", e)

# 检查是否存在 MTP 相关节点
try:
    ninfo = get("/object_info")
    nodes = list(ninfo.keys())
    mtp_nodes = [x for x in nodes if 'mtp' in x.lower() or 'draft' in x.lower()]
    print("\n=== MTP/draft 相关节点 ===")
    print(mtp_nodes or "无")
except Exception as e:
    print("node err:", e)
