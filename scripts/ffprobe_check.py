# -*- coding: utf-8 -*-
"""用 ffprobe 检查视频文件时长/编码。"""
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
FF = r"D:\Comfyui\python\ffmpeg.EXE"
path = sys.argv[1]
r = subprocess.run([FF, "-i", path], capture_output=True, text=True, encoding="utf-8", errors="replace")
print("$ ffmpeg -i")
out = r.stderr or r.stdout
for line in out.splitlines():
    if any(k in line for k in ("Duration", "Video:", "Audio:", "Stream")):
        print(line.strip())
