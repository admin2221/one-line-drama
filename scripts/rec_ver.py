# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
import importlib.metadata as md
print("llama-cpp-python:", md.version("llama-cpp-python"))
print("location:", md.distribution("llama-cpp-python").locate_file("").parent)
