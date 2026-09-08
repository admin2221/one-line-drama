# MiniMax H3 dyt.json 官方导演台提示词模板（Bug 6 调研与落地方案）

> 调研日期：2026-08-28。线上检索不可用（402），本模板从权威本地来源推导：
> 1. **dyt.json 工作流内嵌官方说明**（Comfy-Org MiniMax H3 ref2va 模板的 MarkdownNote）
> 2. **ToonFlow 模型提示词库**（`toonflow_skills/modelPrompt/video/`：Seedance 2.0 / 通用 / Wan2.6）
> 3. **dyt.json 自带的官方提示词样例**（MiniMaxH3ReferenceToVideo 节点的 Input Text 示例）

---

## 1. 官方对 dyt.json（ref2va）提示词的要求（原文摘录）

来自 dyt.json 的 MarkdownNote（官方 Comfy-Org 模板说明）：

> - **prompt**: reference the inputs by tag, in the exact order they were connected,
>   for example `<Picture 1>`, `<Video 1>`, `<Audio 1>`, then describe the target scene, motion, and audio
> - **ref_image_size**: `match` scales references down to the generation's resolution (faster);
>   `max` keeps up to a 2048px short edge for **stronger identity fidelity** (cost: speed)
> - **Sampler**: `res_multistep`; `beta`/`normal` scheduler outperforms `simple` for reference-heavy prompts
> - **Native stereo audio**: voice, sound effects, and music are modeled jointly in a single forward pass
> - **Ref2va's output is very sensitive to prompt wording**; matching the reference tags precisely and
>   being explicit about **which reference drives which part** of the shot tends to work best.

官方样例（工作流内嵌 Input Text）的格式结构：

```
<镜头场景设定>
图1是视频的首帧，
（0-3秒）<动作/运镜/情绪/台词>；
（3-6秒）<动作/运镜/情绪/台词>。
```

---

## 2. 官方导演台提示词模板（本工程落地版）

`factory/minimax_prompt.py::build_dyt_shot_prompt` 现已按以下结构输出（每镜头一个）：

```
<场景设定>。
整体视觉风格：<style>。
图1是视频的首帧[，图2保持场景与整体风格一致][，图3保持关键物品外观一致]。
  全程以对应参考图锁定人物身份、服饰颜色、场景与物品外观，禁止自行改动。
人物定妆锁定（本镜头出场角色外观必须与对应参考图完全一致，服饰颜色、款式、发型不得改变）：
- <Picture N> = <角色名>：<英文定妆prompt，含主色>（外观完全锁定参考图，不变形不变色）
画面站位：<左/右/中，主次与朝向>；站位在整段视频中保持不变，不得左右互换、不得离开画面。
（X-Y秒）<画面动作、运镜与情绪>；（X-Y秒）…      ← 各段时间相加 = 镜头时长
对白（请逐句由指定角色清晰说出，全程简体中文普通话，禁止夹杂英文或其他语言）：
<d>[Chinese] （<Picture N> 中的<角色名>）说："<台词>"。 </d>
声音：<场景> 的环境底噪作为背景衬底，人声对白清晰前置、占据主导，嘴型与台词同步。
  音效与配乐保持连续不突兀，音画同步。
全片简体中文普通话，吐字清晰，禁止出现英文、拼音或其他语言文字；保持无字幕、无水印。
```

### 为什么这样能减少抽卡次数（对照官方要求）

| 官方要求 | 本模板落实 | 解决的问题 |
|---|---|---|
| 按连接顺序精确引用标签 | `图1/图2/图3` 与 `ref_images` 顺序一一对应，并由 `_assemble_shot_refs` 反查 `char_<名> → <Picture N>` | 身份/场景/物品错绑 |
| 明确哪些参考驱动哪部分 | 「人物定妆锁定」逐字绑定角色→图片+英文定妆；「图2保持场景」「图3保持物品」 | 服饰颜色不一致、场景漂移 |
| 原生音频一体生成 | 「声音：…环境底噪…人声前置…音效配乐连续」 | 对白吐字不清、音画分离 |
| 标签精确匹配 | 对白逐句 `（<Picture N> 中的<角色名>）说` | 角色A台词被B讲出 |
| 语言一致性 | `<d>[Chinese]` + 兜底「全片简体中文普通话…禁止英文」 | 出现其他语言 |
| 位置连贯 | 「画面站位」+ shot.position 字段（剧本导演/分幕扩写已要求 LLM 输出） | 人物站位错乱 |

### 配套改动
- `--ref-image-size max`（CLI）/ GUI「参考图保真max」：官方文档明确 `max` 身份保真更强；代价稍慢。
- 角色定妆图统一追加 `full body, standing facing camera, front view, …clear clothing colors` 框架，
  保证 H3 参考图能锁定颜色与外观（`drama_factory._generate_reference_images`）。
- 场景参考图自动追加全局 `style` 后缀，锁定场景氛围一致性。
- 六段式（six_section/director）同步接入说话人绑定 + 站位 + 语言锁定。

---

## 3. 分镜图片（首帧/参考图）要求

dyt.json 中 图1=视频首帧（角色定妆图），图2=场景，图3=物品。工程现已保证：

1. **角色定妆图**：英文定妆 prompt（含年龄/脸型/发型/发色/服饰款式+主色）+ 全身站姿框架，
   作为 图1 首帧与人物身份锚点。
2. **场景图**：场景描述 + 全局风格后缀，作为 图2 场景锚点。
3. **物品图**：物品描述，作为 图3 物品锚点（有物品的镜头才生成）。
4. 每镜头 refs 由 `_assemble_shot_refs` 按「出场角色（按 characters 顺序）→ 场景 → 物品」组装，
   prompt 中的 图N 与输入顺序严格一致。

---

## 4. 待办/说明
- 官方建议 Sampler `res_multistep` + `beta/normal` scheduler：dyt.json 工作流内已配置，
  本工程不改动工作流采样器；如需在代码里强制，可扩展 `--scheduler` 参数（当前 generator 默认 euler/simple 仅用于内置回退节点图）。
- 若 ComfyUI 上已装 `minimax_h3_ref2va_pruned_int8_convrot.safetensors`，工作流直接可用。
