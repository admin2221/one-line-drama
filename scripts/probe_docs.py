# -*- coding: utf-8 -*-
import sys, re, urllib.request, urllib.error
sys.stdout.reconfigure(encoding="utf-8")

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, r.read().decode("utf-8","replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8","replace")
    except Exception as e:
        return 0, str(e)[:200]

for u in ["https://docs.api.nvidia.com/nim/reference/models-1",
          "https://docs.nvidia.com/nim/visual-genai/latest/getting-started.html"]:
    st, body = get(u)
    print(f"== {u}  {st} len {len(body)}")
    if st == 200:
        wan = [x for x in list(dict.fromkeys(re.findall(r'[A-Za-z0-9_\-/\.]*wan[A-Za-z0-9_\-/\.]*', body, re.I))) if x]
        print("   wan mentions:", wan[:10])
        # 找 genai/video endpoints
        g = list(dict.fromkeys(re.findall(r'https://ai\.api\.nvidia\.com/v1/[A-Za-z0-9_\-/\.]+', body)))
        print("   ai.api endpoints:", g[:10])
    print()
