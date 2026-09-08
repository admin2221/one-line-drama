# -*- coding: utf-8 -*-
"""把新的 GUI + 安装向导 + 引擎发布到 G:\短剧项目\成品安装包。"""
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")
SRC = r"D:\Comfyui\comfyui-drama"
DST = r"G:\短剧项目\成品安装包"


def cp(src_name, dst_dir, dst_name=None):
    """把 dist 下 src_name 直接复制到 dst_dir（强制覆盖）。"""
    os.makedirs(dst_dir, exist_ok=True)
    shutil.copy2(os.path.join(SRC, "dist", src_name),
                 os.path.join(dst_dir, dst_name or src_name))


# --- 根目录：直接使用版（强制更新为新版）---
cp("drama-cli-onefile.exe", DST, "drama-cli.exe")
cp("drama-gui.exe", DST)
cp("drama-keygen.exe", DST)
# 使用说明
shutil.copy2(os.path.join(SRC, "deploy", "InstallFiles", "使用说明.txt"),
             os.path.join(DST, "使用说明.txt"))

# --- 安装向导 ---
setup_dir = os.path.join(DST, "安装向导")
os.makedirs(setup_dir, exist_ok=True)
for item in os.listdir(setup_dir):
    p = os.path.join(setup_dir, item)
    if os.path.isdir(p) and item != "InstallFiles":
        shutil.rmtree(p, ignore_errors=True)

cp("drama-setup.exe", setup_dir, "短剧安装向导.exe")
inst = os.path.join(setup_dir, "InstallFiles")
# 清空旧 InstallFiles 再复制，避免残留旧版
if os.path.isdir(inst):
    shutil.rmtree(inst, ignore_errors=True)
os.makedirs(inst, exist_ok=True)
cp("drama-cli-onefile.exe", inst, "drama-cli.exe")
cp("drama-gui.exe", inst)
cp("drama-keygen.exe", inst)
shutil.copy2(os.path.join(SRC, "assets", "drama_icon.png"),
             os.path.join(inst, "drama_icon.png"))
shutil.copy2(os.path.join(SRC, "deploy", "InstallFiles", "使用说明.txt"),
             os.path.join(inst, "使用说明.txt"))

print("发布到 G:\\短剧项目\\成品安装包 OK")
print("  根目录: drama-cli.exe / drama-gui.exe / drama-keygen.exe / 使用说明.txt")
print("  安装向导/短剧安装向导.exe + InstallFiles(引擎+GUI+生成器+图标+说明)")
