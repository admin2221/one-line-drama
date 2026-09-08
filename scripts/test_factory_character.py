# -*- coding: utf-8 -*-
"""测试定妆图阶段：LLM 增强 -> Z-Image 生成 -> 下载 -> 上传 input。"""
import sys
import os
import time
sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, r"D:\Comfyui\comfyui-drama")
from factory.client import ComfyClient
from factory.drama_factory import run_and_get_text, run_and_get_outputs, find_media
from factory import generator

CHARACTER = "A young Chinese delivery man, square jaw, short black hair, wearing a yellow raincoat and black delivery uniform"

client = ComfyClient()
out_dir = r"D:\Comfyui\comfyui-drama\output\_test_character"
os.makedirs(out_dir, exist_ok=True)

print("=== 1) LLM 视觉概念设计师增强 ===")
api = generator.build_image_enhance_prompt(CHARACTER)
enhanced = run_and_get_text(client, api)
print("增强后:", (enhanced or "")[:200])

print("=== 2) Z-Image 生成定妆图 ===")
z_api = generator.build_zimage_prompt(enhanced or CHARACTER, generator.CHAR_PREFIX)
t0 = time.time()
entry = run_and_get_outputs(client, z_api)
fn, sub, typ = find_media(entry)
print(f"图片输出: {fn} | sub={sub} | type={typ} | 耗时 {time.time()-t0:.0f}s")
if not fn:
    sys.exit(1)

local = os.path.join(out_dir, "character.png")
client.view_image(fn, sub, typ, save_to=local)
print("已下载:", local, os.path.getsize(local), "bytes")

print("=== 3) 上传到 ComfyUI input ===")
up = client.upload_image(local)
print("上传返回:", up)
print("input 文件名:", up.get("name"))
