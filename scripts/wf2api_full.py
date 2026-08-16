"""Convert canvas workflow to API prompt - full fidelity:
Widget values are filled in schema declaration order (required then optional),
skipping slots that have links. Ports with links map to [node_id, slot].
"""
import json
import sys
import urllib.request
import urllib.parse

API = "http://127.0.0.1:8188"
INFO_CACHE = {}


def get_info(node_type):
    if node_type not in INFO_CACHE:
        try:
            with urllib.request.urlopen(f"{API}/object_info/{urllib.parse.quote(node_type)}", timeout=8) as r:
                INFO_CACHE[node_type] = json.loads(r.read().decode()).get(node_type, {})
        except Exception:
            INFO_CACHE[node_type] = {}
    return INFO_CACHE[node_type]


def widget_order(node_type):
    """Ordered widget names per schema: required then optional (schema order preserved)."""
    info = get_info(node_type)
    inp = info.get("input", {}) or {}
    names = []
    for sec in ("required", "optional"):
        for name, spec in (inp.get(sec, {}) or {}).items():
            if is_widget(spec):
                names.append(name)
    return names


def get_widget_spec(node_type, name):
    info = get_info(node_type)
    inp = info.get("input", {}) or {}
    for sec in ("required", "optional"):
        spec = (inp.get(sec, {}) or {}).get(name)
        if spec is not None:
            return spec
    return None


WIDGET_TYPES = {"INT", "FLOAT", "STRING", "BOOLEAN", "COMBO", "SEED", "STYLE", "FILENAMES",
                "NUMBER", "XINT", "XSTRING", "XFLOAT", "BATCH", "BOX", "IMAGEUPLOAD", "AUDIOUPLOAD",
                "COMFY_DYNAMICCOMBO_V3", "COMFY_COMBO", "COMFY_STRING", "COMFY_INT", "COMFY_FLOAT",
                "COMFY_BOOLEAN"}


def is_widget(spec):
    """widget: spec[0] is a list (combo options), or spec[0] is a primitive type name.
    port: spec[0] is a node-type string like MODEL/CLIP/VAE."""
    if not isinstance(spec, list) or not spec:
        return False
    t = spec[0]
    if isinstance(t, list):
        return True  # combo
    return isinstance(t, str) and t in WIDGET_TYPES


def dynamic_combo_subnames(spec, key):
    """Return sub-widget names for the selected option of a COMFY_DYNAMICCOMBO_V3."""
    opts = (spec[1] or {}).get("options", [])
    for opt in opts:
        if opt.get("key") == key:
            sub = opt.get("inputs", {}) or {}
            names = []
            for sec in ("required", "optional"):
                for name in (sub.get(sec, {}) or {}).keys():
                    names.append(name)
            return names
    return []


def workflow_to_api(wf):
    nodes = {n["id"]: n for n in wf["nodes"]}
    link_map = {}
    for l in wf["links"]:
        link_map[l[0]] = (l[1], l[2], l[3], l[4])

    prompt = {}
    for n in wf["nodes"]:
        if n.get("mode", 0) in (2, 4):  # bypass (2) / muted (4)
            continue
        nid = str(n["id"])
        inputs = {}
        linked = set()
        for inp in n.get("inputs", []):
            if inp.get("link") is not None and inp["link"] in link_map:
                src_id, src_slot, _, _ = link_map[inp["link"]]
                inputs[inp["name"]] = [str(src_id), src_slot]
                linked.add(inp["name"])
        wnames = widget_order(n["type"])
        wv = n.get("widgets_values", []) or []
        wi = 0
        for wn in wnames:
            # skip port-typed schema inputs (clip/vae/model etc.)
            spec = get_widget_spec(n["type"], wn)
            if spec is None:
                continue  # not a widget (port)
            if wi >= len(wv):
                break
            # COMFY_DYNAMICCOMBO_V3: widgets_values holds [combo_key, sub_value(s), ...]
            if spec[0] == "COMFY_DYNAMICCOMBO_V3":
                key = wv[wi]
                subnames = dynamic_combo_subnames(spec, key)
                if wn in inputs or wn in linked:
                    wi += 1 + len(subnames)
                else:
                    inputs[wn] = key
                    for j, sn in enumerate(subnames):
                        inputs[f"{wn}.{sn}"] = wv[wi + 1 + j]
                    wi += 1 + len(subnames)
                continue
            if wn in inputs or wn in linked:
                # linked widget: consume wv index, keep link
                if wn == "seed" and wi + 1 < len(wv) and wv[wi + 1] in ("randomize", "fixed"):
                    wi += 2
                else:
                    wi += 1
                continue
            # unlinked widget: assign value
            if wn == "seed" and wi + 1 < len(wv) and wv[wi + 1] in ("randomize", "fixed"):
                inputs[wn] = wv[wi]
                wi += 2
            else:
                inputs[wn] = wv[wi]
                wi += 1
        prompt[nid] = {"class_type": n["type"], "inputs": inputs}
    return prompt


if __name__ == "__main__":
    wf = json.load(open(sys.argv[1], encoding="utf-8"))
    p = workflow_to_api(wf)
    out = sys.argv[2] if len(sys.argv) > 2 else sys.argv[1].replace(".json", "_api.json")
    json.dump(p, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Converted {len(p)} nodes -> {out}")
