# -*- coding: utf-8 -*-
"""短剧生成器 CLI 打包入口。

把 comfyui-drama/factory 打包为可执行 exe。
用法（等价于 python -m factory.drama_factory）：
    drama-cli.exe "故事梗概" [--target-seconds 540] [--llm qwen3.5] ...
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

# PyInstaller 打包后在 _MEIPASS/_internal 解包；引擎在 rel/comfyui-drama 下
_HERE = os.path.dirname(os.path.abspath(__file__))
for cand in (_HERE,
             os.path.join(_HERE, "factory"),
             os.path.join(_HERE, "comfyui-drama"),
             os.getcwd()):
    if cand not in sys.path:
        sys.path.insert(0, cand)


def main():
    from factory.drama_factory import main as factory_main
    return factory_main()


if __name__ == "__main__":
    sys.exit(main())
