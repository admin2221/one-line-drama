# -*- coding: utf-8 -*-
"""Probe node input/output schemas for the drama factory build."""
import json
import urllib.request

API = "http://127.0.0.1:8188"


def get_info(node_type):
    try:
        with urllib.request.urlopen(f"{API}/object_info/{node_type}", timeout=10) as r:
            data = json.loads(r.read().decode())
            return data.get(node_type, {})
    except Exception as e:
        return {"error": str(e)}


def dump(node_type, limit=4000):
    n = get_info(node_type)
    print("=" * 60)
    print("NODE:", node_type)
    if "error" in n:
        print("ERROR:", n["error"])
        return
    inp = n.get("input", {}) or {}
    out = n.get("output", {}) or {}
    print("--- required ---")
    for name, spec in (inp.get("required", {}) or {}).items():
        t = spec[0] if isinstance(spec, list) else spec
        print(f"  {name}: {t}")
    print("--- optional ---")
    for name, spec in (inp.get("optional", {}) or {}).items():
        t = spec[0] if isinstance(spec, list) else spec
        print(f"  {name}: {t}")
    print("--- outputs ---")
    if isinstance(out, dict):
        for name, spec in out.items():
            t = spec[0] if isinstance(spec, list) else spec
            print(f"  {name}: {t}")


if __name__ == "__main__":
    import sys
    for nt in sys.argv[1:]:
        dump(nt)
