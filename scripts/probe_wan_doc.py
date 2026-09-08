# -*- coding: utf-8 -*-
import sys, re, urllib.request, urllib.error
sys.stdout.reconfigure(encoding="utf-8")

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8","replace")

for path in ["api/wan2.2-animate.html", "api/wan2.2.html"]:
    url = "https://docs.nvidia.com/nim/visual-genai/latest/" + path
    try:
        body = get(url)
    except Exception as e:
        print("skip", path, e); continue
    print(f"===== {path} len {len(body)}")
    # 找 ai.api genai URL / invoke
    g = list(dict.fromkeys(re.findall(r'https://ai\.api\.nvidia\.com/v1/[A-Za-z0-9_\-/\.]+', body)))
    print("ai.api/genai endpoints:", g[:20])
    # 找 wan 相关的 curl / 端点 / nvcf
    n = list(dict.fromkeys(re.findall(r'nvcf[^"\'\s<]{3,80}|pexec[^"\'\s<]{0,80}', body)))
    print("nvcf/pexec refs:", n[:10])
    # 提取包含 wan2.2-animate 的代码行
    print("--- curl/code with wan2.2-animate ---")
    for m in list(re.finditer(r'wan2\.2-animate', body, re.I))[:3]:
        seg = body[m.start()-80:m.start()+220]
        seg = seg.replace('&lt;','<').replace('&gt;','>').replace('&amp;','&').replace('\\n','\n')
        print(seg)
        print("   ----")
