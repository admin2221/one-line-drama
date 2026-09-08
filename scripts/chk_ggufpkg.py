# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
try:
    import gguf
    print("gguf version:", getattr(gguf, "__version__", "?"))
    print("path:", gguf.__file__)
except ImportError as e:
    print("no gguf:", e)
