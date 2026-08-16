# -*- coding: utf-8 -*-
"""Fix LLM hang: fixed seed + strengthen stop instruction in system_prompt."""
import json, shutil, sys, datetime
sys.stdout.reconfigure(encoding="utf-8")
P = r"D:\Comfyui\Comfyui\user\default\workflows\一句话短剧20镜头.json"
BAK = P + ".bak_llmfix_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
shutil.copy2(P, BAK)
print("backup ->", BAK)

wf = json.load(open(P, encoding="utf-8"))
nodes = {n["id"]: n for n in wf["nodes"]}
n103 = nodes[103]
wv = n103["widgets_values"]

# wv layout for llama_cpp_instruct_adv:
# [0]preset [1]custom_prompt [2]system_prompt [3]inference_mode [4]max_frames [5]max_size
# [6]seed [7]control_after_generate [8]force_offload [9]save_states
print("before seed control:", wv[7])

# 1) fix seed
wv[7] = "fixed"

# 2) strengthen stop instruction
sys_prompt = wv[2]
stop_note = "\n【最重要】输出最后一个 } 后必须立即停止生成，绝对不要输出任何解释、总结、重复或多余文字。"
if "立即停止" not in sys_prompt:
    wv[2] = sys_prompt.rstrip() + stop_note

n103["widgets_values"] = wv
json.dump(wf, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("after seed control:", wv[7])
print("system_prompt tail:", wv[2][-120:])
print("saved")
