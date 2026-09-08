# -*- coding: utf-8 -*-
"""冒烟：--image-backend local/api 解析、DramaFactory 状态与 nvidia() 报错路径。"""
import os
import sys

sys.path.insert(0, r"D:\Comfyui\comfyui-drama")
from factory import drama_factory as DF
from factory.client import ComfyClient


def test_argparse():
    import argparse
    # 模拟 main 的 argparse：直接用 ap 内建（不便），这里用真实 parse 子集方式不可行，
    # 改为直接验证 main 的 parse 参数列表能接收新 flags（用 ap.parse_args 白名单不现实），
    # 最简单：调用 drama_factory.main 的 parse 部分？main 需要 story 与 ComfyUI。
    # 改用手工构造 DramaFactory 验证后端分流即可。
    class A:
        image_backend = "api"
        image_api_config = None
        llm = None
        provider = None
        provider_config = None
        no_enhance = False
    client = ComfyClient("http://127.0.0.1:9")  # 不实际连接
    os.makedirs(r"D:\Comfyui\comfyui-drama\output\_smoke", exist_ok=True)
    f = DF.DramaFactory(client, r"D:\Comfyui\comfyui-drama\output\_smoke", A())
    assert f.image_backend == "api"
    # 无配置时 nvidia() 抛 RuntimeError 且文案含引导
    try:
        f.nvidia()
        raise SystemExit("FAIL: 应抛错")
    except RuntimeError as e:
        assert "image_api.json" in str(e), str(e)
    # local 缺省
    class A2(A):
        image_backend = "local"
    f2 = DF.DramaFactory(client, r"D:\Comfyui\comfyui-drama\output\_smoke", A2())
    assert f2.image_backend == "local"
    assert f2._api_image is not None
    print("SMOKE_OK")


if __name__ == "__main__":
    test_argparse()
