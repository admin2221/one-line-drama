# -*- coding: utf-8 -*-
"""Locate imageio-ffmpeg binary + check ComfyUI dirs."""
import imageio_ffmpeg
import os

print("imageio-ffmpeg:", imageio_ffmpeg.get_ffmpeg_exe())

base = r"D:\Comfyui\Comfyui"
for sub in ["output", "input", "temp"]:
    p = os.path.join(base, sub)
    print(sub, "->", p, "exists:", os.path.isdir(p))

# video subfolder used by h3hbai SaveVideo
vp = os.path.join(base, "output", "video")
print("output/video exists:", os.path.isdir(vp))
