# -*- coding: utf-8 -*-
"""Dump full JSON of a node schema (for links/outputs)."""
import json
import sys
import urllib.request

API = "http://127.0.0.1:8188"


def get_info(node_type):
    try:
        with urllib.request.urlopen(f"{API}/object_info/{node_type}", timeout=10) as r:
            data = json.loads(r.read().decode())
            return data.get(node_type, {})
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    for nt in sys.argv[1:]:
        n = get_info(nt)
        print("=" * 60)
        print("NODE:", nt)
        print(json.dumps(n, ensure_ascii=False, indent=1)[:6000])
