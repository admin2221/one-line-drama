# -*- coding: utf-8 -*-
"""重启 ComfyUI：kill 占用 8188 的进程 -> 等待端口释放 -> 以原参数后台拉起。

自动探测端口 PID，避免硬编码失效。
"""
import os
import re
import socket
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

BASE = r"D:\Comfyui\Comfyui"  # main.py 所在目录
PORT = 8188
LOG = os.path.join(r"D:\Comfyui", "comfyui_restart.log")
CMDLINE = [r"D:\Comfyui\python\python.exe", "main.py",
           "--preview-method", "none", "--cuda-malloc",
           "--port", "8188", "--listen", "0.0.0.0",
           "--extra-model-paths-config", r"D:\Comfyui\Comfyui\extra_model_paths.yaml"]


def find_pid_on_port(port):
    """返回监听 port 的 PID，找不到返回 None。"""
    out = subprocess.run(["netstat", "-ano"], capture_output=True,
                         text=True, encoding="utf-8", errors="replace").stdout
    for line in out.splitlines():
        if f":{port}" in line and "LISTENING" in line:
            m = re.findall(r"\d+$", line.strip())
            if m:
                return int(m[-1])
    return None


# 1) 关闭占用端口的旧进程（循环杀，可能有残留）
while True:
    pid = find_pid_on_port(PORT)
    if pid is None:
        print(f"端口 {PORT} 无监听进程")
        break
    print("关闭旧进程", pid, "...")
    subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                   capture_output=True, text=True)
    time.sleep(2)

# 2) 等待端口释放
deadline = time.time() + 60
while time.time() < deadline:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        if s.connect_ex(("127.0.0.1", PORT)) != 0:
            break
    time.sleep(1)
print("端口已释放（或超时）")

# 3) 后台拉起
with open(LOG, "w", encoding="utf-8") as f:
    p = subprocess.Popen(CMDLINE, stdout=f, stderr=subprocess.STDOUT,
                         creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                         cwd=BASE)
print("新进程 PID:", p.pid)
print("日志:", LOG)
