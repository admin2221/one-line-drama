# -*- coding: utf-8 -*-
import sys, re, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
req = urllib.request.Request("https://build.nvidia.com/wan-ai/wan2.2-animate-2-14b",
                             headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "replace")

# 找 input_image_b64 位置，提取其后较长片段（含完整调用）
idx = html.find("input_image_b64")
print("idx:", idx)
# 在含 bash 的字段附近提取。查找脚本被 \\n 转义，先还原
for m in re.finditer(r'input_image_b64', html):
    start = max(0, m.start()-60)
    print("\n===== snippet around input_image_b64 =====")
    # 还原转义
    seg = html[start:m.start()+2600]
    seg = seg.replace('\\n', '\n').replace('\\u003e', '>').replace('\\u0026','&').replace('\\"','"').replace('\\u00a0',' ')
    print(seg)
    break
