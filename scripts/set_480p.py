# -*- coding: utf-8 -*-
"""Set 480p: ResolutionSelector megapixels 0.1 -> 0.4 (=> 864x480 @16:9, multiple 32)."""
import json, shutil, sys, datetime
sys.stdout.reconfigure(encoding="utf-8")
P = r"D:\Comfyui\Comfyui\user\default\workflows\一句话短剧20镜头.json"
BAK = P + ".bak_480p_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
shutil.copy2(P, BAK)
print("backup ->", BAK)

wf = json.load(open(P, encoding="utf-8"))
nodes = {n["id"]: n for n in wf["nodes"]}

n155 = nodes[155]
print("before ResolutionSelector wv:", n155["widgets_values"])
n155["widgets_values"] = ["16:9 (Widescreen)", 0.4, 32]
print("after  ResolutionSelector wv:", n155["widgets_values"])

json.dump(wf, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("saved. ResolutionSelector now 0.4 MP => 864x480 (480p)")

# verify computation
import math
total = 0.4 * 1024 * 1024
scale = math.sqrt(total / (16 * 9))
w = round(16 * scale / 32) * 32
h = round(9 * scale / 32) * 32
print(f"computed H3 output: {w}x{h}")
