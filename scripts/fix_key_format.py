# -*- coding: utf-8 -*-
"""Fix v5: GetObjectFromJson key format.
get_dict_attribute() requires array index in the form "shots.[0]" (bracket),
NOT "shots.0" (plain dot number). Fix all GetObjectFromJson keys.
"""
import json, shutil, sys, datetime
sys.stdout.reconfigure(encoding="utf-8")

WF = r"D:\Comfyui\Comfyui\user\default\workflows\一句话短剧全自动流水线.json"
BAK = WF + ".bak_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
shutil.copy2(WF, BAK)
print("backup ->", BAK)

wf = json.load(open(WF, encoding="utf-8"))
fixed = 0
for n in wf["nodes"]:
    if n["type"] == "GetObjectFromJson":
        wv = n.get("widgets_values", [])
        if wv and isinstance(wv[0], str):
            old = wv[0]
            new = old.replace(".0", ".[0]").replace(".1", ".[1]").replace(".2", ".[2]").replace(".3", ".[3]")
            # careful: replace only trailing index like "shots.0" -> "shots.[0]"
            import re
            new2 = re.sub(r"^([\w]+)\.(\d+)$", r"\1.[\2]", old)
            if new2 != old:
                wv[0] = new2
                fixed += 1
                print(f"GetObjectFromJson({n['id']}): key '{old}' -> '{new2}'")

wf["last_node_id"] = max(n["id"] for n in wf["nodes"])
wf["last_link_id"] = max(l[0] for l in wf["links"])
with open(WF, "w", encoding="utf-8") as f:
    json.dump(wf, f, ensure_ascii=False, indent=1)
print(f"fixed {fixed} GetObjectFromJson keys. saved.")
