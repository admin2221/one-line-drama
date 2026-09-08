# -*- coding: utf-8 -*-
"""视频拼接：用 ComfyUI 自带 ffmpeg 将多个镜头 mp4 合并为完整短剧。"""
import os
import subprocess
import sys

_CANDIDATE_FFMPEG = [
    r"D:\Comfyui\python\ffmpeg.exe",
    r"D:\Comfyui\python\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe",
    r"D:\Comfyui\python\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg.exe",
]


def find_ffmpeg():
    for p in _CANDIDATE_FFMPEG:
        if os.path.isfile(p):
            return p
    import shutil
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    return None


def trim_first_frames(src, dst, n=17, fps=24, ffmpeg=None):
    """裁掉视频开头 n 帧废帧后重新编码保存为 dst（帧精确，视频/音轨同步裁剪）。

    用于配合 dyt 工作流的「首部废帧」：每个镜头多生成 17 帧，保存前裁掉开头 17 帧，
    规避 H3 首段画面闪烁/黑帧/崩坏。视频用 trim=start_frame（帧精确）；
    音轨若存在按 n/fps 秒同步裁剪（atrim），不存在则自动忽略。
    返回 True=成功；False=失败（调用方可回退用原片）。
    """
    ffmpeg = ffmpeg or find_ffmpeg()
    if not ffmpeg:
        return False
    try:
        a_start = float(int(n)) / float(fps or 24)
    except Exception:
        a_start = float(n) / 24.0
    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", src,
           "-map", "0:v:0", "-map", "0:a?",
           "-vf", f"trim=start_frame={int(n)},setpts=PTS-STARTPTS",
           "-af", f"atrim=start={a_start:.6f},asetpts=PTS-STARTPTS",
           "-c:v", "libx264", "-crf", "18", "-preset", "fast",
           "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", dst]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    except Exception:
        return False
    return (r.returncode == 0 and os.path.isfile(dst)
            and os.path.getsize(dst) > 0)


def concat_videos(file_list, output, ffmpeg=None, reencode=False):
    """拼接 file_list（有序）到 output。默认 -c copy，失败则重编码。"""
    if not file_list:
        raise ValueError("空镜头列表，无法拼接")
    if len(file_list) == 1:
        # 单镜头直接复制
        data = open(file_list[0], "rb").read()
        with open(output, "wb") as f:
            f.write(data)
        return output

    ffmpeg = ffmpeg or find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("未找到 ffmpeg，无法拼接（请检查 D:\\Comfyui\\python\\ffmpeg.exe）")

    # concat demuxer 需要 list 文件
    list_file = output + ".concat.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for p in file_list:
            # ffmpeg concat 需要正斜杠且转义单引号
            safe = os.path.abspath(p).replace("\\", "/").replace("'", "'\\''")
            f.write(f"file '{safe}'\n")

    def run(args):
        return subprocess.run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error"] + args,
                              capture_output=True, text=True, encoding="utf-8", errors="replace")

    if not reencode:
        r = run(["-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", output])
        if r.returncode == 0:
            os.remove(list_file)
            return output
        # 回退到重编码
    r = run(["-f", "concat", "-safe", "0", "-i", list_file,
             "-c:v", "libx264", "-crf", "20", "-preset", "medium",
             "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p", output])
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg 拼接失败：{r.stderr}")
    os.remove(list_file)
    return output
