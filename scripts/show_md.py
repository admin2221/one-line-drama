# -*- coding: utf-8 -*-
import sys, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
req = urllib.request.Request("https://build.nvidia.com/wan-ai/wan2.2-animate-2-14b.md",
                             headers={"User-Agent": "Mozilla/5.0"})
md = urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "replace")
print(md)
