# -*- coding: utf-8 -*-
import json, sys, urllib.request
sys.stdout.reconfigure(encoding="utf-8")

h = json.load(urllib.request.urlopen("http://127.0.0.1:8188/history", timeout=10))
if not h:
    print("history 空"); sys.exit()
for pid, rec in list(h.items())[-2:]:
    st = rec.get("status", {})
    print("PID:", pid, "| status:", st.get("status_str"), "| completed:", st.get("completed"))
    outs = rec.get("outputs", {})
    for nid, o in outs.items():
        if "text" in o:
            print(f"  node {nid} text:", str(o.get("text"))[:300])
