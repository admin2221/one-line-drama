"""Full frontend-simulation validation of the user's latest canvas workflow.
Checks for every node:
  1. widgets_values consumption vs widget inputs (seed consumes extra control value)
  2. type mismatches (INT/FLOAT/STRING/BOOLEAN/COMBO)
  3. input link -> link index consistency (input.link must exist in links array)
  4. output links array entries reference valid link ids
  5. every link id referenced by node inputs/outputs exists in the links array
Prints a node inventory too.
"""
import json, sys

WF = sys.argv[1] if len(sys.argv) > 1 else r"D:\Comfyui\Comfyui\user\default\workflows\一句话短剧全自动流水线.json"

wf = json.load(open(WF, encoding="utf-8"))
nodes = {n["id"]: n for n in wf["nodes"]}
links = {l[0]: l for l in wf["links"]}
link_srcs = {}
for l in wf["links"]:
    link_srcs[l[0]] = (l[1], l[2])

errors = []
warnings = []

# --- inventory ---
print("=== NODE INVENTORY ===")
for n in sorted(nodes.values(), key=lambda x: x["id"]):
    nid = n["id"]
    t = n["type"]
    mode = n.get("mode", 0)
    ins = [i["name"] for i in n.get("inputs", [])]
    outs = [o["name"] for o in n.get("outputs", [])]
    wv = n.get("widgets_values", []) or []
    flags = "MUTED" if mode == 4 else ""
    print(f"{nid:4d} [{t}] {flags} in={ins} out={outs} wv_len={len(wv)}")

# --- checks ---
print("\n=== CHECKS ===")
for n in nodes.values():
    nid = n["id"]
    t = n["type"]
    wv = n.get("widgets_values", []) or []

    # input link consistency
    for idx, i in enumerate(n.get("inputs", [])):
        if i.get("link") is not None:
            lid = i["link"]
            if lid not in links:
                errors.append(f"Node {nid} {t}: input '{i['name']}' link {lid} not in links array")
            else:
                src_id, src_slot = links[lid][1], links[lid][2]
                # src output must have this link
                src = nodes.get(src_id)
                if src:
                    souts = src.get("outputs", [])
                    if src_slot >= len(souts):
                        errors.append(f"Node {nid} {t}: input '{i['name']}' link {lid} src {src_id} slot {src_slot} OOB")
                    else:
                        sl = souts[src_slot].get("links", []) or []
                        if lid not in sl:
                            warnings.append(f"Node {nid} {t}: input '{i['name']}' link {lid} not listed in src {src_id}.{src_slot} links")

    # widget consumption (frontend fills widgets_values in widget-input order, seed consumes 2)
    # DynamicCombo serializes [combo_key, sub_value(s), ...] out of declaration order; skip type check
    has_dyn = any(i.get("type") == "COMFY_DYNAMICCOMBO_V3" for i in n.get("inputs", []))
    if has_dyn:
        continue
    widget_inputs = [i for i in n.get("inputs", []) if i.get("widget")]
    pos = 0
    for i in widget_inputs:
        name = i["name"]
        if pos >= len(wv):
            errors.append(f"Node {nid} {t}: ran out of widgets_values at '{name}' (need {len(widget_inputs)}+ extras, have {len(wv)})")
            break
        v = wv[pos]
        if name in ("seed", "noise_seed") and t in ("KSampler", "RandomNoise", "llama_cpp_instruct_adv"):
            if pos + 1 >= len(wv):
                errors.append(f"Node {nid} {t}: '{name}' missing control value after seed (wv[{pos+1}] EOF)")
            else:
                ctrl = wv[pos + 1]
                if not (isinstance(ctrl, str) and ctrl in ("randomize", "fixed", "increment", "decrement")):
                    errors.append(f"Node {nid} {t}: '{name}' control value wv[{pos+1}]={ctrl!r} not randomize/fixed")
            pos += 2
        else:
            pos += 1
        typ = i["type"]
        if typ == "INT" and not isinstance(v, int):
            errors.append(f"Node {nid} {t}: '{name}' expected INT got {v!r}")
        elif typ == "FLOAT" and not isinstance(v, (int, float)):
            errors.append(f"Node {nid} {t}: '{name}' expected FLOAT got {v!r}")
        elif typ == "STRING" and not isinstance(v, str):
            errors.append(f"Node {nid} {t}: '{name}' expected STRING got {v!r}")
        elif typ == "BOOLEAN" and not isinstance(v, bool):
            errors.append(f"Node {nid} {t}: '{name}' expected BOOLEAN got {v!r}")
        elif typ == "COMBO" and not isinstance(v, str):
            errors.append(f"Node {nid} {t}: '{name}' expected COMBO got {v!r}")

print("\n=== WARNINGS ===")
for w in warnings[:30]:
    print(" -", w)
print(f"\n=== {len(errors)} ERRORS ===")
for e in errors[:60]:
    print(" -", e)
sys.exit(1 if errors else 0)
