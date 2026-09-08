# -*- coding: utf-8 -*-
"""复制 exe 打包产物 + 使用说明到 G:\\短剧项目\\成品安装包。"""
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")
SRC = r"D:\Comfyui\comfyui-drama\dist"
DST = r"G:\短剧项目\成品安装包"

os.makedirs(DST, exist_ok=True)
# onedir 版（带完整依赖目录）
onedir = os.path.join(SRC, "drama-cli")
if os.path.isdir(onedir):
    shutil.copytree(onedir, os.path.join(DST, "drama-cli-onedir"), dirs_exist_ok=True)
    print("onedir OK")
# onefile 单文件版
onefile = os.path.join(SRC, "drama-cli-onefile.exe")
if os.path.isfile(onefile):
    shutil.copy2(onefile, os.path.join(DST, "drama-cli.exe"))
    print("onefile OK")

readme = """# 短剧生成器 · 一键生成竖屏短剧

## 两个安装形态（已打包，无需 Python）
1. **drama-cli.exe** —— 单文件独立版（自带 Python+引擎，双击/命令行运行，无外部依赖）
2. **drama-cli-onedir/** —— 目录版（解压后运行其中 drama-cli.exe，启动稍快）

## 使用（命令行）
```
drama-cli.exe "一句话故事梗概" 
drama-cli.exe "..." --target-seconds 540 --llm qwen3.5 --megapixels 0.2 
drama-cli.exe "..." --characters-json characters\\xxx_characters.json --output 输出目录
```

## 常用参数
- `--target-seconds 秒` 目标总时长（3-15 分钟均可）
- `--llm qwen3.5|qwen3.8` 剧本 LLM（推荐 qwen3.5）
- `--megapixels 0.2` 分辨率（竖屏 352×608）
- `--steps 16` 视频采样步数
- `--characters-json 路径` 预置角色JSON（保证一致性）
- `--resume` 断点续跑（跳过已完成镜头）
- `--plan-only` 只规划剧本预览，不生成画面
- `--script-json 路径` 复用已有剧本

## 运行前提
- 本机 ComfyUI 需在 127.0.0.1:8188 运行（本 exe 是客户端，向本机 ComfyUI 提交生成）
- 需要的模型/工作流均在 ComfyUI 中加载

## 产物
每次生成输出到 `output\\<标题>\\`：
- `final_drama.mp4` 完整成片
- `script.json` 完整剧本
- `character_*.png` / `scene_*.png` / `prop_*.png` 参考图
- `shots\\shot_*.mp4` 逐镜头视频
"""
with open(os.path.join(DST, "使用说明.txt"), "w", encoding="utf-8") as f:
    f.write(readme)
print("使用说明 OK →", DST)
