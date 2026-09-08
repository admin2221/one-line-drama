# -*- coding: utf-8 -*-
import json, sys, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
d = json.load(urllib.request.urlopen("http://127.0.0.1:8188/queue", timeout=10))
print("running:", len(d.get("queue_running", [])), " pending:", len(d.get("queue_pending", [])))
