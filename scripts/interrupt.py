# -*- coding: utf-8 -*-
"""中断 ComfyUI 当前任务并清队列。"""
import urllib.request

req = urllib.request.Request("http://127.0.0.1:8188/interrupt", method="POST")
try:
    r = urllib.request.urlopen(req, timeout=10)
    print("interrupt:", r.read()[:100])
except Exception as e:
    print("err:", e)
