# -*- coding: utf-8 -*-
"""生成短剧生成器图标 drama_icon.ico（胶片+星光主题）。"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
try:
    from PIL import Image, ImageDraw
except ImportError:
    print("NO-PILLOW")
    sys.exit(2)

S = 256
img = Image.new("RGB", (S, S), (18, 20, 34))
d = ImageDraw.Draw(img)

# 渐变背景（竖向深蓝→紫）
for y in range(S):
    t = y / S
    d.line([(0, y), (S, y)], fill=(int(30 + 20 * t), int(40 + 80 * t), int(80 + 150 * t)))

# 胶片外框（圆角矩形）
box = (24, 24, S - 24, S - 24)
d.rounded_rectangle(box, radius=30, fill=(10, 12, 22), outline=(255, 215, 100), width=6)

# 胶片两侧齿孔（小方块）
for gy in range(40, S - 40, 26):
    d.rectangle((40, gy, 52, gy + 14), fill=(255, 255, 255))
    d.rectangle((S - 52, gy, S - 40, gy + 14), fill=(255, 255, 255))

# 中央放映窗口
d.rounded_rectangle((56, 70, S - 56, S - 70), radius=12, fill=(255, 255, 255))

# 放映窗内容：一座山 + 星星（电影画面）
cx = S // 2
d.polygon([(cx - 46, S - 78), (cx - 8, S - 128), (cx + 42, S - 78)], fill=(120, 100, 220))
d.ellipse((cx - 16, cx - 34, cx + 14, cx - 20), fill=(255, 215, 100))
# 星星
dots = [(120, 96), (150, 88), (170, 110), (130, 120)]
for (x, y) in dots:
    d.polygon([(x, y - 6), (x + 2, y - 2), (x + 6, y - 2), (x + 3, y + 1), (x + 4, y + 6),
               (x, y + 3), (x - 4, y + 6), (x - 3, y + 1), (x - 6, y - 2), (x - 2, y - 2)],
              fill=(255, 255, 255))

out = r"D:\Comfyui\comfyui-drama\assets\drama_icon.ico"
os.makedirs(os.path.dirname(out), exist_ok=True)
img.save(out, sizes=[(256, 256), (64, 64), (48, 48), (32, 32), (16, 16)])
img.save(r"D:\Comfyui\comfyui-drama\assets\drama_icon.png")
print("ICON_OK", out)
