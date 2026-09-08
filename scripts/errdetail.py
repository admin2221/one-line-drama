# -*- coding: utf-8 -*-
import json, sys, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
h = json.load(urllib.request.urlopen("http://127.0.0.1:8188/history", timeout=10))
pid = "19771f31-6aff-4ab8-9751-22bd8afdcc9b"
rec = h.get(pid)
if not rec:
    print(pid, "不在 history 中"); sys.exit()
print("status keys:", list(rec.get("status", {}).keys()))
st = rec.get("status", {})
print("status_str:", st.get("status_str"), "completed:", st.get("completed"))
for msg in st.get("messages", []):
    print(" msg:", str(msg)[:400])
