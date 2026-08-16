# ComfyUI 一句话短剧流水线

把**一句话故事梗概**自动扩写成一部 **20 镜头短剧视频**。

## 流程

```
一句话梗概
  → LLM 剧本生成（Qwen3.5-9B，输出 20 镜头 JSON）
  → 镜头 1：Z-Image 参考图 → H3 视频 → RTX 超分 → 合成 → 提取尾帧
  → 镜头 2：H3 视频（用镜头 1 尾帧做首帧）→ RTX → 合成 → 尾帧
  → ...（严格串行，镜头 N 依赖镜头 N-1 尾帧）
  → 镜头 20
  → mergeVideos 串联 20 个片段
  → 保存完整短剧
```

## 特性

- **20 镜头自动生成**：一句话 → 完整短剧，全程无人工干预
- **严格串行**：尾帧数据依赖链 + `ImpactExecutionOrderController`，镜头 1→20 顺序执行，避免 VRAM 抢占
- **480p 输出**：864×480（16:9），H3 视频生成
- **RTX 超分**（可选）：每个镜头独立 `RTXVideoSuperResolution`，带全局总开关
- **帧数限制**：每镜头 3-5 秒（≤124 帧），避免 VAEDecode GPU OOM
- **递增 seed**：20 个镜头 seed 递增，画面有差异且可复现

## 目录结构

```
.
├── workflows/
│   └── 一句话短剧20镜头.json      # 主工作流（566 节点）
└── scripts/
    ├── gen_20shots.py             # 20 镜头扩展生成器
    ├── gen_master.py              # 主生成器
    ├── add_switch_and_chaining.py # RTX 开关 + 尾帧串行链
    ├── add_shotlist.py            # 分镜列表节点
    ├── fix_seed_merge.py          # 递增 seed + 强制 merge 串行
    ├── fix_oom2.py                # OOM 修复（帧数上限 124）
    ├── fix_llm.py                 # LLM seed 固定 + 停止指令
    ├── fix_json_truncation2.py    # JSON 截断修复（max_tokens 4096）
    ├── set_480p.py                # 480p 分辨率设置
    ├── wf2api_full.py             # 工作流 → API prompt 转换器
    ├── deep_check2.py             # 工作流完整性校验
    ├── check_widgets.py           # widget 加载校验
    ├── remove_useless.py          # 清理无用节点
    ├── reachability.py            # 可达性分析
    ├── run_drama_pipeline.py      # 运行流水线
    ├── submit_run.py              # 提交工作流到 ComfyUI
    ├── monitor_loop.py            # 执行进度监控
    └── validate_wf.py             # 工作流验证
```

## 使用方法

### 1. 导入工作流

把 `workflows/一句话短剧20镜头.json` 放入 ComfyUI 的 workflows 目录：

```
ComfyUI/user/default/workflows/
```

在 ComfyUI 界面加载该工作流。

### 2. 设置一句话剧情

找到节点 `① 一句话剧情`（node 100），写入你的故事梗概，例如：

> 古代美女在河边捡到一支玫瑰，意外穿越到了罗马帝国

### 3. 运行

点击 **Queue Prompt** 即可。也可以命令行提交：

```bash
python scripts/wf2api_full.py <工作流.json> <输出api.json>
python scripts/submit_run.py
python scripts/monitor_loop.py
```

## 依赖

| 组件 | 说明 |
|------|------|
| ComfyUI | 最新版 |
| ComfyUI-llama-cpp_vlm | LLM 剧本生成（Qwen3.5-9B） |
| MiniMax H3 | 视频生成（i2v） |
| comfyui-art-venture | GetObjectFromJson / JSON 工具 |
| comfyui-impact-pack | ImpactExecutionOrderController |
| comfyui-easy-media | easy mergeVideos / imageSwitch |
| XB_ToolBox | ResolutionSelector |
| nvvfx SDK | RTX 超分（可选） |

## 硬件要求

- **16GB VRAM**（RTX 4060 Ti 级别），H3 视频生成 + RTX 超分
- **≥32GB 系统内存**（merge 链用 torch.cat 合并帧）

## 已知问题

- **RTX 4x 超分会导致 merge OOM**：RTX 4x 把 480p 放大到 3456×1920（每帧 76MB float32），`easy mergeVideos` 的 `torch.cat` 合并 20 镜头时系统内存爆炸。当前默认**关闭 RTX 总开关**（node 900 = false），走 480p 原生帧。若要启用 RTX，需将 merge 改为 ffmpeg 流式合并（磁盘）而非 torch.cat（内存）。
- **LLM 生成偶发卡死**：已通过固定 seed + 强化停止指令缓解。
