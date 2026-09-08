# -*- coding: utf-8 -*-
"""plan-only：只生成剧本(3角色+场景+物品)并打印结构，不生成画面。"""
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\Comfyui\comfyui-drama")
from factory.client import ComfyClient
import factory.drama_factory as df
import argparse

STORY = ("深夜老书店即将拆迁，店主沈唐收到一本能照见亡者的旧日记；"
         "神秘女读者叶澜在书页夹缝发现真相，警探宋远追查一系列城市失踪案，"
         "三人于最后一夜在书店对峙，解开二十年前的旧案。")
OUT = r"D:\Comfyui\comfyui-drama\output\drama_3char_3min"

ap = argparse.ArgumentParser()
df.main  # no-op
args = argparse.Namespace(
    story=STORY, story_opt=None, url="http://127.0.0.1:8188",
    output=OUT, steps=16, megapixels=0.2,
    aspect="9:16 (Portrait Widescreen)", width=None, height=None,
    no_enhance=False, resume=False, reencode=False, script_json=None,
    target_seconds=165, plan_only=True, llm="qwen3.8")

client = ComfyClient(base_url=args.url)
h = client.health()
if "error" in h:
    raise RuntimeError(f"无法连接 ComfyUI：{h}")
import os
os.makedirs(OUT, exist_ok=True)
factory = df.DramaFactory(client, OUT, args)
factory.log(f"短剧工厂启动（plan），输出：{OUT}")
script = factory.generate_script(STORY)
lines = []
lines.append("=== PLAN 结构 ===")
lines.append("characters: %d %s" % (len(script.get("characters", [])),
             [c.get("name") for c in script.get("characters", [])]))
lines.append("scenes: %s" % list(script.get("scenes", {}).keys()))
lines.append("props: %s" % list(script.get("props", {}).keys()))
shots = script.get("shots", [])
lines.append("shots: %d 总秒: %d" % (len(shots), sum(int(str(s.get('duration', '5')).strip() or 5) for s in shots)))
for s in shots:
    lines.append("  shot %s | %s | refs=%s | scene_ref=%s | props=%s" % (
        s.get('shot'), s.get('scene'), s.get('character_refs'),
        s.get('scene_ref'), s.get('props')))
report = "\n".join(lines)
print(report)
with open(r"D:\Comfyui\comfyui-drama\plan_3char_out.txt", "w", encoding="utf-8") as f:
    f.write(report)
