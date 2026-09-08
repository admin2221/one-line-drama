# -*- coding: utf-8 -*-
"""测试单镜头 H3 ref2va 视频生成（定妆图已上传为 character.png）。"""
import sys
import os
import time
sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, r"D:\Comfyui\comfyui-drama")
from factory.client import ComfyClient
from factory.drama_factory import run_and_get_outputs, find_media
from factory import generator

client = ComfyClient()
out_dir = r"D:\Comfyui\comfyui-drama\output\_test_shot"
os.makedirs(out_dir, exist_ok=True)

shot = {
    "video_prompt": "A young Chinese delivery man, square jaw, short black hair, wearing a yellow raincoat, running frantically in heavy rain on wet city street, camera follows behind him, modern city night, neon blue and red lights, cinematic",
    "dialogue": "订单要超时了，快一点！",
    "duration_sec": 3.0,
}

print("=== 单镜头 H3 ref2va 生成（3s，steps=16）===")
api = generator.build_shot_video_prompt(shot, "character.png", {"steps": 16})
t0 = time.time()
entry = run_and_get_outputs(client, api)
fn, sub, typ = find_media(entry, exts=(".mp4", ".webm", ".mov"))
print(f"视频输出: {fn} | sub={sub} | type={typ} | 耗时 {time.time()-t0:.0f}s")
if not fn:
    print("!!! 未获取到视频输出，history outputs:", list(entry.get("outputs", {}).keys()))
    sys.exit(1)

local = os.path.join(out_dir, "shot_001.mp4")
client.view_image(fn, sub, typ, save_to=local)
print("已下载:", local, os.path.getsize(local), "bytes")
