"""Simulate frontend canvas widget loading to verify widget_values order matches widget inputs.
Frontend fills widgets_values in the order widgets appear in node.inputs (with "widget" key),
consuming one value per widget; seed widgets consume 2 values (seed + randomize control)."""
import json
import sys

SEED_NODES = {"KSampler", "RandomNoise", "llama_cpp_instruct_adv", "llama_cpp_parameters"}
# nodes where seed is followed by a randomize control in widgets_values
SEED_WITH_CONTROL = {"KSampler", "RandomNoise", "llama_cpp_instruct_adv"}


def check(path):
    wf = json.load(open(path, encoding="utf-8"))
    errors = []
    for n in wf["nodes"]:
        t = n["type"]
        wv = n.get("widgets_values", []) or []
        widget_inputs = [i for i in n.get("inputs", []) if i.get("widget")]
        # DynamicCombo serializes [combo_key, sub_value(s), ...] out of declaration order; skip
        if any(i.get("type") == "COMFY_DYNAMICCOMBO_V3" for i in widget_inputs):
            continue
        # Simulate frontend: consume widgets_values in widget_input order;
        # seed/noise_seed consume an extra control value ("randomize"/"fixed").
        pos = 0
        for i in widget_inputs:
            name = i["name"]
            if pos >= len(wv):
                errors.append(f"Node {n['id']} {t}: ran out of widgets_values at {name}")
                break
            v = wv[pos]
            # seed widgets: value + control (only for sampler-style nodes)
            if name in ("seed", "noise_seed") and t in SEED_WITH_CONTROL:
                if pos + 1 >= len(wv) or wv[pos + 1] not in ("randomize", "fixed", True, False):
                    errors.append(f"Node {n['id']} {t}: {name} missing control value after seed: wv[{pos+1}]={wv[pos+1] if pos+1 < len(wv) else 'EOF'}")
                pos += 2
            else:
                pos += 1
            typ = i["type"]
            if typ == "INT" and not isinstance(v, int):
                errors.append(f"Node {n['id']} {t}: {name} expected INT got {v!r}")
            elif typ == "FLOAT" and not isinstance(v, (int, float)):
                errors.append(f"Node {n['id']} {t}: {name} expected FLOAT got {v!r}")
            elif typ == "STRING" and not isinstance(v, str):
                errors.append(f"Node {n['id']} {t}: {name} expected STRING got {v!r}")
            elif typ == "BOOLEAN" and not isinstance(v, bool):
                errors.append(f"Node {n['id']} {t}: {name} expected BOOLEAN got {v!r}")
            elif typ == "COMBO" and not isinstance(v, str):
                errors.append(f"Node {n['id']} {t}: {name} expected COMBO got {v!r}")
        # trailing values in widgets_values beyond widget_inputs (non-widget virtual widgets) are allowed
    if errors:
        print(f"=== {len(errors)} WIDGET ISSUES ===")
        for e in errors[:40]:
            print(" -", e)
        sys.exit(1)
    else:
        print(f"=== WIDGET LOAD OK: {len(wf['nodes'])} nodes ===")


if __name__ == "__main__":
    check(sys.argv[1])
