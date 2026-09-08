# -*- coding: utf-8 -*-
"""验证 3 分钟短剧成品：时长、流、解码、镜头完整性。"""
import os, re, subprocess, sys
sys.stdout.reconfigure(encoding="utf-8")

FF = r"D:\Comfyui\python\ffmpeg.exe"
base = r"D:\Comfyui\comfyui-drama\output\gujing_3min"

def probe(path):
    r = subprocess.run([FF, "-hide_banner", "-i", path], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    err = r.stderr
    dur = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", err)
    audio = re.search(r"Audio:\s*(\w+)", err)
    video = re.search(r"Video:\s*(\w+)", err)
    return {
        "duration": (int(dur.group(1))*3600 + int(dur.group(2))*60 + float(dur.group(3))) if dur else None,
        "size": os.path.getsize(path),
        "video": video.group(1) if video else None,
        "audio": audio.group(1) if audio else None,
    }

# 1) 最终成品
f = os.path.join(base, "final_drama.mp4")
info = probe(f)
print(f"final_drama.mp4: 时长 {info['duration']:.2f}s ({info['duration']/60:.1f} 分钟) | {info['size']//1024//1024} MB | 视频 {info['video']} | 音频 {info['audio']}")

# 2) 解码验证
r = subprocess.run([FF, "-hide_banner", "-i", f, "-t", "5", "-f", "null", "-"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print("前5秒解码:", "OK" if r.returncode == 0 else f"FAIL\n{r.stderr[-400:]}")

# 3) 镜头完整性
d = os.path.join(base, "shots")
files = sorted(x for x in os.listdir(d) if x.endswith(".mp4"))
print(f"镜头文件: {len(files)}/45")
sizes = [os.path.getsize(os.path.join(d, x)) for x in files]
print(f"  最小 {min(sizes)//1024} KB / 最大 {max(sizes)//1024} KB / 平均 {sum(sizes)//1024//len(sizes)} KB")
