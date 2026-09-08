# -*- coding: utf-8 -*-
import sys, os
sys.stdout.reconfigure(encoding="utf-8")
import struct

MODEL = r"D:\Comfyui\Comfyui\models\LLM\Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-IQ3_M.gguf"

def read_string(f):
    n = struct.unpack("<Q", f.read(8))[0]
    return f.read(n).decode("utf-8", "replace")
def read_u32(f): return struct.unpack("<I", f.read(4))[0]
def read_u64(f): return struct.unpack("<Q", f.read(8))[0]
def skip_value(f, atype):
    if atype==0: f.seek(1,1)
    elif atype==1: f.seek(8,1)
    elif atype in (2,5,6): f.seek(4,1)
    elif atype in (3,7,12): f.seek(8,1)
    elif atype==4: n=struct.unpack("<Q",f.read(8))[0]; f.seek(n,1)
    elif atype==8: n=struct.unpack("<Q",f.read(8))[0]; f.seek(n,1)
    elif atype==9: n=struct.unpack("<Q",f.read(8))[0]
        # array: skip element, then n elems
    elif atype in (10,12,13,14,15,16,17,18):
        # array types for some gguf versions
        pass

with open(MODEL,"rb") as f:
    assert f.read(4)==b"GGUF"
    version=read_u32(f); tensor_count=read_u64(f); kv_count=read_u64(f)
    bc=None
    for _ in range(kv_count):
        key=read_string(f)
        atype=read_u32(f)
        if key=="qwen35.block_count":
            bc=struct.unpack("<I",f.read(4))[0]; print("qwen35.block_count =", bc)
            break
        # skip value per type
        if atype in (0,): f.seek(1,1)
        elif atype in (2,5,6): f.seek(4,1)
        elif atype in (3,7,12,1): f.seek(8,1)
        elif atype in (4,8): n=struct.unpack("<Q",f.read(8))[0]; f.seek(n,1)
        else:
            # generic array: byte for type + item_type, then u64 count * item
            pass

gguf_layers = int(bc) or 32
vram_factor=1.55
size_gb=os.path.getsize(MODEL)*vram_factor/(1024**3)
layer_size=size_gb/gguf_layers
print("gguf_layers:",gguf_layers,"| size:%.2fGB per-layer:%.4fGB"%(size_gb,layer_size))
for vl in (12,21,16):
    print(f"  vram_limit={vl} → n_gpu_layers={max(1,int(vl/layer_size))}")
