# -*- coding: utf-8 -*-
"""Full schema of key nodes."""
import json
import urllib.request

API = "http://127.0.0.1:8188"
for nt in ["ResolutionSelector", "MiniMaxH3ImageToVideo", "MiniMaxH3ReferenceToVideo"]:
    with urllib.request.urlopen(f"{API}/object_info/{nt}", timeout=8) as r:
        n = json.loads(r.read().decode()).get(nt, {})
    print("=" * 60)
    print("NODE:", nt)
    print(json.dumps(n.get("input", {}), ensure_ascii=False, indent=1)[:5000])
