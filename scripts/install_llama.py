# -*- coding: utf-8 -*-
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
WHL = r"D:\Comfyui\wheels\llama_cpp_python-0.3.48+cu130-cp312-cp312-win_amd64.whl"
r = subprocess.run([sys.executable, "-m", "pip", "install", "--force-reinstall",
                    "--no-deps", WHL], capture_output=True, text=True, encoding="utf-8", errors="replace")
print(r.stdout[-3000:])
if r.returncode:
    print("STDERR:", r.stderr[-2000:])
    sys.exit(1)
import importlib.metadata as md
print("新版本:", md.version("llama-cpp-python"))
