# -*- coding: utf-8 -*-
"""验证最终短剧视频：时长、流、可解码性（用 ffmpeg -i 文本输出解析）。"""
import os, re, subprocess, sys
sys.stdout.reconfigure(encoding="utf-8")

FF = r"D:\Comfyui\python\ffmpeg.exe"
base = r"D:\Comfyui\comfyui-drama\output\_e2e_test"

def probe(path):
    r = subprocess.run([FF, "-hide_banner", "-i", path], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    err = r.stderr
    dur = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", err)
    streams = re.findall(r"Stream #\d+:\d+[^:]*:\s*(\w+):\s*([\w/]+)(?:[,\s]*\((\w+)\))?", err)
    audio = re.search(r"Audio:\s*(\w+)", err)
    video = re.search(r"Video:\s*(\w+)", err)
    return {
        "duration": (int(dur.group(1))*3600 + int(dur.group(2))*60 + float(dur.group(3))) if dur else None,
        "size": os.path.getsize(path),
        "video": video.group(1) if video else None,
        "audio": audio.group(1) if audio else None,
    }

for name in ["shots/shot_001.mp4", "shots/shot_002.mp4", "final_drama.mp4"]:
    info = probe(os.path.join(base, name))
    print(f"{name}: 时长 {info['duration']:.2f}s | {info['size']}B | 视频 {info['video']} | 音频 {info['audio']}")
