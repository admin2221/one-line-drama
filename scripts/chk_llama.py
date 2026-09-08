# -*- coding: utf-8 -*-
import subprocess, sys
sys.stdout.reconfigure(encoding="utf-8")
PY = r"D:\Comfyui\python\python.exe"
r = subprocess.run([PY, "-c", "import llama_cpp, sys; print('llama_cpp', llama_cpp.__version__); print('py', sys.version.split()[0])"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print(r.stdout)
print(r.stderr[-400:] if r.returncode else "")
