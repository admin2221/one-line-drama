# -*- coding: utf-8 -*-
"""生成 8 镜头试片剧本 JSON（约 40s，全链路验证）。"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
story = "雨夜，一名外卖骑手在城中村送单，撞见十年前失踪的哥哥，追债黑衣人逼近。"

shots = [
    {"shot": 1, "scene": "暴雨接单", "duration": "5",
     "image_prompt": "A young Chinese man in yellow raincoat riding delivery motorcycle through torrential rain, neon city street, cinematic",
     "dialogue": "这单送到老宅？",
     "video_prompt": "A young Chinese man in yellow raincoat riding delivery motorcycle, low-angle tracking, rain streaking, neon reflections"},
    {"shot": 2, "scene": "雨巷骑行", "duration": "5",
     "image_prompt": "The courier pedals through narrow flooded alley, headlight beam piercing rain, cold blue tones",
     "dialogue": "",
     "video_prompt": "Dynamic tracking shot through flooded alley, wheel splashing water, handheld energy"},
    {"shot": 3, "scene": "老宅浮现", "duration": "5",
     "image_prompt": "A shabby old house emerges from the rain, lone warm light in window, overgrown courtyard",
     "dialogue": "",
     "video_prompt": "Slow push-in toward old house doorway, rain on roof, eerie atmosphere"},
    {"shot": 4, "scene": "门口停步", "duration": "5",
     "image_prompt": "The courier hesitates at the threshold, rain dripping off hood, dim doorway ahead",
     "dialogue": "有人吗？",
     "video_prompt": "Close-up on courier's hesitant eyes, then swing to dark doorway, suspense"},
    {"shot": 5, "scene": "哥哥开门", "duration": "5",
     "image_prompt": "A gaunt older man in worn coat opens door, pale face, shock in eyes, dim interior light",
     "dialogue": "陈默？是我……陈影。",
     "video_prompt": "Door creaks open revealing brother Chen Ying, slow zoom on his pale face, flash of recognition"},
    {"shot": 6, "scene": "血盒交接", "duration": "5",
     "image_prompt": "Chen Ying presses a blood-stained box into his younger brother's hands, trembling, hallway dark",
     "dialogue": "盒里是救命的药，别让外面的人拿到。",
     "video_prompt": "Close-up on hands transferring blood-stained box, tense two-shot, rain pounding outside"},
    {"shot": 7, "scene": "黑衣人逼近", "duration": "5",
     "image_prompt": "Black-clad men emerge from alley, bats raised, blocking escape, torrential rain",
     "dialogue": "",
     "video_prompt": "Wide low-angle shot of black-clad men approaching, handheld tracking, menacing"},
    {"shot": 8, "scene": "雨夜逃离", "duration": "5",
     "image_prompt": "The brothers sprint through rain, Chen Ying shielding the box, flashes of pursuit, neon glow",
     "dialogue": "跑！",
     "video_prompt": "Dynamic tracking sprint through rain, close on clenched fists and box, explosive escape"},
]

script = {
    "title": "雨夜快递 · 试片",
    "character": "Chinese male, 28, lean angular face, short black hair, soaked yellow raincoat",
    "style": "modern rainy night, cold blue tones, neon reflections, cinematic",
    "shots": shots,
    "_note": "8镜头全链路试片验证",
}
out = r"D:\Comfyui\comfyui-drama\output\techtest_8shot\script.json"
import os
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w", encoding="utf-8") as f:
    json.dump(script, f, ensure_ascii=False, indent=2)
print("剧本已写入:", out, len(shots), "镜头, 总时长", sum(int(s["duration"]) for s in shots), "s")
