# -*- coding: utf-8 -*-
"""Fix GPU OOM in 20-shot workflow:
  - ComfyMathExpression frame cap: min(240,...) -> min(124,...) (5s, validated safe)
  - system_prompt duration range: 5-15 -> 3-5 (shorter shots avoid VAEDecode OOM)
  Resolution stays 480p (0.4 MP) per user request.
"""
import json, shutil, sys, datetime
sys.stdout.reconfigure(encoding="utf-8")

WF = r"D:\Comfyui\Comfyui\user\default\workflows\一句话短剧20镜头.json"
BAK = WF + ".bak_oom2_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
shutil.copy2(WF, BAK)
print("backup ->", BAK)

wf = json.load(open(WF, encoding="utf-8"))

NEW_FORMULA = "min(124, max(5, round(a * 24)) + (5 - (max(5, round(a * 24)) % 17)) % 17)"

mth_fixed = 0
for n in wf["nodes"]:
    if n["type"] == "ComfyMathExpression":
        wv = n.get("widgets_values", [])
        for i, v in enumerate(wv):
            if isinstance(v, str) and "round(a * 24)" in v:
                wv[i] = NEW_FORMULA
                mth_fixed += 1
        n["widgets_values"] = wv
print(f"ComfyMathExpression fixed: {mth_fixed}")

llm = next(n for n in wf["nodes"] if n["id"] == 103)
wv = llm["widgets_values"]
sp = wv[2]
old = sp
sp = sp.replace("5 到 15", "3 到 5")
sp = sp.replace("5 到 8", "3 到 5")
wv[2] = sp
print("system_prompt duration updated:", "changed" if sp != old else "UNCHANGED (check text)")

wf["last_node_id"] = max(n["id"] for n in wf["nodes"])
wf["last_link_id"] = max(l[0] for l in wf["links"])
json.dump(wf, open(WF, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("saved.")
