# -*- coding: utf-8 -*-
"""单测：模拟 PyInstaller frozen 场景，验证 find_engine 用 sys.executable 目录定位引擎。"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\Comfyui\comfyui-drama\gui")
import drama_gui

# 构造一个仅包含 drama-cli.exe 的假"安装目录"
fake_appdir = r"D:\Comfyui\comfyui-drama\dist\gui_test"
fake_engine = os.path.join(fake_appdir, "drama-cli.exe")
if not os.path.isfile(fake_engine):
    # 用现有引擎复制一份
    os.makedirs(fake_appdir, exist_ok=True)
    import shutil
    shutil.copy2(r"D:\Comfyui\comfyui-drama\dist\drama-cli-onefile.exe", fake_engine)

# 模拟 frozen：__file__ 指向临时目录(不存在引擎)，sys.executable 指向"安装目录"
real_exec = sys.executable
try:
    sys.frozen = True
    sys.executable = os.path.join(fake_appdir, "drama-gui.exe")
    drama_gui.__file__ = os.path.join("C:\\_MEIPASS_tmp", "drama_gui.py")  # 模拟临时解压目录
    found = drama_gui.find_engine()
    print("find_engine 结果:", found)
    if found and found.replace("\\", "/").endswith("gui_test/drama-cli.exe"):
        print("FROZEN_OK: 正确用 sys.executable 目录定位到引擎")
    else:
        print("FROZEN_FAIL")
finally:
    sys.frozen = False
    sys.executable = real_exec
