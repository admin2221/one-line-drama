# -*- coding: utf-8 -*-
"""校验 短剧工厂.json 结构完整性：链接引用、输入输出槽位、可达性。"""
import json
import sys
sys.stdout.reconfigure(encoding="utf-8")

WF = r"D:\Comfyui\Comfyui\user\default\workflows\短剧工厂.json"
wf = json.load(open(WF, encoding="utf-8"))
nodes = {n["id"]: n for n in wf["nodes"]}
links = wf["links"]
errors = []

# 1) 每条 link 的端点节点/槽位必须存在
def slot_index(io_list, slot):
    """slot 可为整数下标或名称，返回匹配的槽位 dict。"""
    if isinstance(slot, int):
        return io_list[slot] if 0 <= slot < len(io_list) else None
    for x in io_list:
        if x.get("name") == slot:
            return x
    return None

for l in links:
    lid, src, src_slot, dst, dst_slot, typ = l
    if src not in nodes:
        errors.append(f"link {lid}: 源节点 {src} 不存在")
        continue
    if dst not in nodes:
        errors.append(f"link {lid}: 目标节点 {dst} 不存在")
        continue
    s = nodes[src]
    d = nodes[dst]
    src_out = slot_index(s.get("outputs", []), src_slot)
    dst_in = slot_index(d.get("inputs", []), dst_slot)
    if src_out is None:
        errors.append(f"link {lid}: 源 {src}({src_slot}) 输出槽位不存在")
    elif isinstance(src_slot, int) and "links" not in src_out:
        errors.append(f"link {lid}: 源 {src}({src_slot}) 输出槽位未记录 links")
    if dst_in is None:
        errors.append(f"link {lid}: 目标 {dst}({dst_slot}) 输入槽位不存在")
    elif dst_in.get("link") != lid:
        errors.append(f"link {lid}: 目标 {dst}({dst_slot}) 输入槽位未记录 link {lid}")

# 2) 节点声明了 link 但 LINKS 里没有对应项
declared = set()
for n in nodes.values():
    for inp in n.get("inputs", []):
        if inp.get("link") is not None:
            declared.add(inp["link"])
actual = {l[0] for l in links}
for d in declared - actual:
    errors.append(f"节点输入声明了 link {d} 但链接表不存在")

# 3) 悬空输入（shape=7 的输入必须连上；除输出节点外）
output_nodes = {"SaveVideo", "ShowText|pysssss"}
for n in nodes.values():
    if n["type"] in output_nodes:
        continue
    for inp in n.get("inputs", []):
        if inp.get("link") is None and inp.get("shape") == 7:
            # shape 7 = 普通输入（非 optional）
            errors.append(f"节点 {n['id']} {n['type']} 输入 {inp['name']} 未连接")

# 4) 可达性：从所有输出节点反向 BFS
terminal_ids = [nid for nid, n in nodes.items() if n["type"] in output_nodes]
rev = {}
for l in links:
    rev.setdefault(l[3], []).append(l)  # dst node id (l[3]) -> links into it
stack = list(terminal_ids)
reachable = set(stack)
while stack:
    nid = stack.pop()
    for l in rev.get(nid, []):
        src = l[1]
        if src not in reachable:
            stack.append(src)
            reachable.add(src)
unreachable = [nid for nid in nodes if nid not in reachable]
if unreachable:
    for nid in unreachable:
        errors.append(f"节点 {nid} {nodes[nid]['type']} 不可达（未连到任何输出）")

print(f"节点数: {len(nodes)}，链接数: {len(links)}")
if errors:
    print(f"发现 {len(errors)} 个问题：")
    for e in errors[:40]:
        print("  -", e)
    sys.exit(1)
print("OK：全部链接与槽位匹配，所有节点可达。")
