# 短剧工厂（Drama Factory）

一句话生成一部完整竖屏短剧。整合了项目里两个已验证的 ComfyUI 工作流：

- **imageai.json**：`llama_cpp` 视觉概念设计师提示词增强 → **Z-Image turbo** 文生图（8 步）
- **h3hbai.json**：**MiniMax H3 ref2va** 多参视频（参考图 `<Picture 1>` + 原生音频，竖屏 9:16）

## 流程

```
一句话剧情
   │  ① LLM 剧本导演（Qwen3.5-9B）→ 角色定妆 + N 个分镜 JSON
   ▼
   │  ② LLM 视觉概念设计师增强 → Z-Image 生成角色定妆图 → 上传 input
   ▼
   │  ③ 逐镜头 MiniMax H3 ref2va 生成视频（共用定妆图 <Picture 1>，原生音频）
   ▼
   │  ④ 全部镜头 ffmpeg 自动拼接 → final_drama.mp4
```

- **角色一致性**：所有镜头共用同一张定妆图（`ref_image_0`），主角外观一致
- **无限时长**：镜头数由剧本决定，逐镜头循环生成、逐个保存，支持断点续跑
- **逐镜头独立提交**：每镜头一个独立 API prompt，跑完释放显存，规避单一大工作流的 OOM

## 快速开始

在 `D:\Comfyui` 下运行（ComfyUI 服务保持 `http://127.0.0.1:8188` 在线）：

```bat
:: 方式一：直接一句话
python comfyui-drama\factory\drama_factory.py "一个落魄书生在雨夜捡到一枚能穿越时空的古镜"

:: 方式二：断点续跑（跳过已生成的镜头）
python comfyui-drama\factory\drama_factory.py "故事..." --resume

:: 方式三：复用已有剧本 JSON，跳过 LLM 阶段
python comfyui-drama\factory\drama_factory.py --script-json comfyui-drama\output\xxx\script.json
```

## 常用参数

| 参数 | 默认 | 说明 |
|------|------|------|
| `--url` | `http://127.0.0.1:8188` | ComfyUI 地址 |
| `--steps` | `16` | H3 采样步数（越高越精细、越慢） |
| `--megapixels` | `0.4` | H3 分辨率（0.4 ≈ 竖屏 480×864） |
| `--aspect` | `9:16 (Portrait Widescreen)` | 画面比例 |
| `--width` / `--height` | — | 强制分辨率（覆盖比例计算） |
| `--no-enhance` | 关 | 跳过定妆图 LLM 增强 |
| `--resume` | 关 | 断点续跑 |
| `--reencode` | 关 | 拼接时强制重编码 |
| `--script-json` | — | 复用已有剧本，跳过 LLM |
| `--target-seconds` | — | 目标总时长（秒），≥90s 时自动分幕扩写（如 180 → 约 45 镜头） |
| `--plan-only` | 关 | 只生成剧本并预览（镜头数/总时长/预计耗时），不生成画面 |
| `--output` | `output/时间戳` | 输出目录 |

## 输出目录结构

```
output/<时间戳>/
├── script.json        # 剧本（含 character/style/shots）
├── llm_raw.txt        # LLM 原始输出（仅解析失败时生成，供排查）
├── character.png      # 角色定妆图
├── shots/
│   ├── shot_001.mp4
│   └── ...
└── final_drama.mp4    # 完整短剧
```

## 代码结构

```
factory/
├── drama_factory.py   # 主入口：四阶段编排
├── generator.py       # ComfyUI API prompt 生成器（模型/采样常量）
├── client.py          # ComfyUI HTTP 客户端（提交/轮询/上传/下载）
├── concat.py          # ffmpeg 视频拼接
├── prompts.py         # 剧本导演 / 视觉概念设计师提示词
└── prompts/*.txt      # 外部提示词原文（提取自工作流）
```

## 关键实现说明

- **参考图引用**：`MiniMaxH3ReferenceToVideo` 的 `ref_images.ref_image_0` 对应提示词中的 `<Picture 1>`（1-based，见 `comfy/text_encoders/minimax.py`）。定妆图经 `/upload/image` 上传到 input 目录，镜头内用 `LoadImage` 加载。
- **帧数换算**：`duration 秒 → round(dur*24) → snap 到 17k+5 网格`（H3 的 length 约束，124 帧 ≈ 5 秒）。
- **文本输出捕获**：LLM 文本经 `ShowText|pysssss`（output_node）写入 history，由 `client.first_text()` 提取。

## 依赖与硬件

| 组件 | 说明 |
|------|------|
| ComfyUI 0.30.0 | `http://127.0.0.1:8188` |
| ComfyUI-llama-cpp_vlm | LLM 剧本/增强（Qwen3.5-9B） |
| MiniMax H3 (ref2va) | 视频生成 + 原生音频 |
| Z-Image turbo | 角色定妆图 |
| ffmpeg | `D:\Comfyui\python\ffmpeg.exe`（拼接用） |

- **16GB VRAM**（RTX 4060 Ti 级别）即可运行（逐镜头释放显存）。

## 历史方案

旧目录还保留 `一句话短剧20镜头.json`（566 节点单一大工作流，i2v + RTX 超分 + 尾帧串行）供参考，但其 RTX 4x 超分会导致 merge OOM，且单工作流难以断点续跑。新工厂采用逐镜头独立提交 + ffmpeg 磁盘拼接，规避了这些问题。
