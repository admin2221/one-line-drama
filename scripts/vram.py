# -*- coding: utf-8 -*-
import json, sys, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
d = json.load(urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=10))
for dev in d.get("devices", []):
    print("vram total MB:", dev.get("vram_total", 0)//1024//1024,
          "| used MB:", dev.get("vram_used", 0)//1024//1024,
          "| total:", dev.get("name"))
