# -*- coding: utf-8 -*-
"""Fix v2: max_tokens=4096 (node max), ultra-slim system_prompt for 20-shot JSON fit,
temperature 0.4 for deterministic JSON.
"""
import json, shutil, sys, datetime
sys.stdout.reconfigure(encoding="utf-8")

P = r"D:\Comfyui\Comfyui\user\default\workflows\一句话短剧20镜头.json"
# restore from pre-fix backup (the one before 7000 attempt)
BAK_SRC = P + ".bak_20260815_214425"
shutil.copy2(BAK_SRC, P)
print("restored from", BAK_SRC)

wf = json.load(open(P, encoding="utf-8"))

# ---- Fix 1: max_tokens 1024 -> 4096 (node max), temperature -> 0.4 ----
params = next(n for n in wf["nodes"] if n["id"] == 102)
wv = params["widgets_values"]
old_max, old_temp = wv[0], wv[5]
wv[0] = 4096
wv[5] = 0.4
print(f"max_tokens {old_max} -> 4096, temperature {old_temp} -> 0.4")

# ---- Fix 2: ultra-slim system_prompt ----
llm = next(n for n in wf["nodes"] if n["id"] == 103)
new_sp = """你是短剧导演。根据一句话故事梗概，扩写为 20 镜头分镜剧本。人物一致，剧情连贯。

只输出 JSON，第一行以 { 开头，最后一行以 } 结尾，不要其他任何文字。格式：
{
  "title": "标题",
  "shots": [
    {
      "shot": 1,
      "scene": "场景（≤15字）",
      "image_prompt": "英文绘图提示词（≤40词）",
      "dialogue": "对白（≤30字）",
      "video_prompt": "英文运镜（≤25词）",
      "duration": "8"
    }
  ]
}

硬性要求：
- 必须恰好 20 个镜头（shot 1-20）
- image_prompt 和 video_prompt 用英文
- duration 是 5 到 15 之间的整数字符串
- 字段间用逗号分隔，不要省略逗号，不要输出代码块"""
llm["widgets_values"][2] = new_sp
print("system_prompt ultra-slimmed")

with open(P, "w", encoding="utf-8") as f:
    json.dump(wf, f, ensure_ascii=False, indent=1)
print("saved.")
