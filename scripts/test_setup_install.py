# -*- coding: utf-8 -*-
"""真实测试安装逻辑：复制到临时目录 + 创建快捷方式。"""
import os
import sys
import tempfile
import shutil

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\Comfyui\comfyui-drama\deploy")
import drama_setup

app = drama_setup.SetupWizard()

# 用临时目录测试安装流程
temp_dest = os.path.join(tempfile.gettempdir(), "短剧安装测试_zz")
if os.path.exists(temp_dest):
    shutil.rmtree(temp_dest)
app.install_dir.set(temp_dest)
app.desktop_sc.set(False)  # 桌面快捷方式只在真实桌面，测试跳过

# 直接调用安装核心（不弹窗）
app._go_dir()
# 手动触发安装到临时目录
app._install()
print("install_dir =", temp_dest)
for f in sorted(os.listdir(temp_dest)):
    print("  ", f)
print("SETUP_INSTALL_DONE")
