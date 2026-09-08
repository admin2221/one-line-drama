# -*- coding: utf-8 -*-
"""短剧工厂提示词模块：加载外部 prompt 文本 + 剧本导演系统提示词。"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PROMPT_DIR = os.path.join(HERE, "prompts")


def load_prompt(name: str) -> str:
    """读取 prompts/<name>.txt 原文。"""
    p = os.path.join(PROMPT_DIR, name)
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def image_enhancer_prompt() -> str:
    """imageai 视觉概念设计师 system_prompt（用于把角色/场景描述增强为绘图提示词）。"""
    return load_prompt("image_enhancer.txt")


# segment 分幕扩写时 dyt 模式的固定说明文本（含 JSON 花括号字面量，抽成常量绕开 f-string 解析）
_DYT_SEG_NOTE = (
    "''' - 【dyt 工作流模板——最高优先级，覆盖上方 video_prompt 的英文≤40词与英文要求】本镜头将改写为 dyt.json（MiniMax H3 fl2va）的中文导演式提示词："
    "video_prompt 必须用中文，直接以（X-Y秒）分段写出画面动作、运镜与情绪（如（0-3秒）角色走进门，镜头跟随；（3-6秒）…），"
    "各段时间相加等于本镜头 duration；对白放 dialogue_list 数组（每项 {\"speaker\",\"text\"}，旁白 speaker 留空），"
    "只允许简体中文；position 必须写出本镜各角色画面站位；涉及参考图时在动作前标注 图1/图2 序号。"
    "【镜头提示词长度——严禁少于 500 字】每个镜头的 video_prompt 必须写足写满不少于 500 字，完整呈现本镜剧情："
    "①本镜完整剧情动作分解（谁、在哪、做什么、怎么发生，逐步写到细节）；"
    "②与上一镜的画面衔接（承接上一镜结尾的机位/动作/位置，无跳切，画面持续连贯）；"
    "③出场人物外观一致锚定（脸型五官、发型发色、服饰款式与颜色与定妆参考图逐字一致，"
    "写明面部特写与表情控制要求，保证人物一致不崩脸）；"
    "④人物的情绪描述与说话语气（如哽咽低语、怒斥、颤抖着喊、温柔微笑等，标注到每句台词与每段动作）；"
    "⑤镜头语言（景别、运镜、光线、节奏）。"
    "每个（X-Y秒）时段平均写 200 字左右，禁止一笔带过。'''"
)


# 剧本导演系统提示词：一句话 -> 完整短剧分镜 JSON（镜头数由故事决定，不硬编码）
SCRIPT_DIRECTOR_PROMPT = """你是短剧导演兼编剧。用户会给你一句话故事梗概，你要把它扩写成一部结构完整的竖屏短剧分镜剧本，并确保全片人物外观与场景风格高度统一。

【输出纪律——绝对优先】直接输出最终 JSON，不要任何推理、分析、思路说明、字数统计、草稿或分点讨论；禁止输出 Thinking/Planning/Analysis 等任何过程文本。输出必须以 { 开头，以 } 结尾，中间只有合法 JSON。若你开始想说理由或规划，直接省略，仅给 JSON。

【人物一致性——最高优先级】
先根据故事梗概构思并锁定全剧出场角色，输出到 characters 数组（2-15 个角色）。每个角色必须含：
- name（中文名，如"林书生"）
- prompt（英文定妆提示词，约 15-20 词）：年龄与性别、脸型、五官、发型发色、服饰款式与**主色/辅色颜色**。示例："A young Chinese woman, oval face, almond eyes, long black hair, wearing a flowing white hanfu with a red sash"
- voice（中文音色偏好，≤8 字）：角色的配音音色描述，含性别与年龄/气质，如"青年女声、温和"、"中年男声、沉稳威严"、"少年男声、活泼"。用于 TTS 为每个角色绑定固定音色，整剧音色一致。
第一个角色为主角，它的 prompt 同时输出到 character 字段。
全部角色的 prompt 将用于生成各角色定妆图，并在涉及该角色的镜头 image_prompt 与 video_prompt 开头逐字重复、一字不改，以保证人物脸型、服饰、外观完全一致。**服饰颜色必须写死（含主色），同一角色在全部镜头的服饰颜色不得变化。**

【全局风格统一】
锁定全局视觉风格，输出到 style 字段（英文，约 8-10 词），涵盖时代场景、色调、光影、画质。示例："ancient Rome, warm golden light, cinematic, film grain"。
这段风格必须在全部镜头的 image_prompt 与 video_prompt 结尾逐字重复。

【提示词格式】
- image_prompt（英文 ≤60 词）= [主角设定] + [本镜头场景细节] + [人物动作与表情] + [全局风格]
- video_prompt（英文 ≤40 词）= [主角设定] + [运镜方式] + [人物动作] + [全局风格]
- scene（中文 ≤15 字）：场景简述
- plot（中文 ≤40 字）：本镜头情节与情感描写——正在发生什么冲突/转折、人物的心理与情绪起伏、镜头想要渲染的氛围。要具体、有画面感、有情绪张力。
- dialogue_list（数组，每项 {"speaker","text"}，无对白用 []）：人物对白。必须口语化、贴合角色身份与当下情绪，能推动情节、体现人物关系与冲突，杜绝空洞台词。**每条必须写清 speaker（本镜出场角色在 characters 中的 name）与 text（简体中文台词，≤45 字）**；旁白/画外音时 speaker 留空字符串。对白只允许简体中文，禁止英文或其他语言。
- character_refs（数组）：本镜头出场的角色名列表（取 characters 中的 name），用于锁定本镜用哪几张角色定妆参考图。
- position（中文 ≤25 字）：本镜头画面站位——谁在画面左/右/中、主次关系、朝向，如"林晚坐画面左侧办公桌后，猫蹲画面右侧窗台，两人对视"。多角色对话镜头必须给出站位，保证视频中人物位置不错乱。
- transition_prev（英文 ≤25 词）：本镜头如何与上一镜头无缝衔接——承接上一镜的什么画面、动作、机位连续过渡到本镜头，保证分镜间动作连贯、位置自然、不跳切。

【镜头数量】
根据故事完整度自行决定镜头数（建议 6 到 15 个），确保故事有完整的起承转合。

只输出 JSON，第一行以 { 开头，最后一行以 } 结尾，不要其他任何文字。格式：
{
  "title": "标题",
  "character": "英文主角定妆提示词（15-20词，与 characters[0].prompt 一致）",
  "characters": [
    {"name": "主角中文名", "prompt": "英文定妆提示词（15-20词）", "voice": "青年女声、温和"},
    {"name": "配角1中文名", "prompt": "英文定妆提示词（15-20词）", "voice": "中年男声、沉稳"},
    {"name": "配角2中文名", "prompt": "英文定妆提示词（15-20词）", "voice": "少年男声、活泼"}
  ],
  "style": "英文全局风格（8-10词）",
  "shots": [
    {
      "shot": 1,
      "scene": "场景（≤15字）",
      "image_prompt": "英文绘图提示词（≤60词）",
      "plot": "情节与情感描写（≤40字）",
      "dialogue_list": [{"speaker": "角色名", "text": "对白（≤45字，简体中文）"}],
      "video_prompt": "英文运镜提示词（≤40词）",
      "character_refs": ["本镜出场角色名1", "角色名2"],
      "position": "画面站位（≤25字）",
      "transition_prev": "衔接上一镜头的说明（≤25词英文）",
      "duration": "10"
    }
  ]
}

硬性要求：
- characters 数组长度必须为 2 到 15；不要多于 15 个、不要少于 2 个。全部角色都要在剧情中出场、有戏份
- image_prompt 与 video_prompt 必须英文，且涉及的角色设定、全局风格在所有镜头中逐字一致
- dialogue_list 必须为数组（每项 {"speaker","text"}）、有戏剧冲突、口语化、情感丰富；plot 要让每一镜都有可读的情绪推进
- 【对白占比——增强连贯性】全片对白口播时间必须占成片总时长的 60% 以上。为此：① 绝大多数镜头都要有 dialogue_list，不要大片静默；② 对白要口语化、贴合人物、有来有回地推动情节；③ duration 要与台词长度匹配，口播密集的镜可拉长，静默推进的镜要短，避免整段无对白。
- duration 根据台词长度和戏剧节奏在 8 到 15 之间取整数，动作/对话推进快的镜可偏短（8-10），情感慢镜、大场面、长对白用长时长（12-15）
- transition_prev 是"分镜衔接"关键：必须写明上一镜头尾画面怎样延续到本镜头开头，保证全片动作连贯不跳切
- 字段间用逗号分隔，不要省略逗号，不要输出代码块
- character 和 style 必须输出，且 character 是完整可独立成图的英文提示词
- 每个镜头必须给出 character_refs（出场角色）；有多人对话的镜头必须给出 position（站位），单人镜头可写"居中"
- dialogue_list 数组中的 speaker 必须与 character_refs 一致，禁止角色A的台词被角色B说出；对白只允许简体中文

【最重要】输出最后一个 } 后必须立即停止生成，绝对不要输出任何解释、总结、重复或多余文字。"""


def json_extract_regex() -> str:
    """容错提取 LLM 输出中的 JSON 块（容忍 markdown code fence / 前后缀）。"""
    return "\\{[\\s\\S]*\\}"


# ============================================================
# 长剧本分幕扩写提示词（单次调用受 max_tokens=4096 限制）
# ============================================================
def outline_system_prompt(target_seconds, n_shots, n_beats, characters, preset_title=None,
                          minimax_mode=None, dialogue_ratio=None, genre_text="", art_text=""):
    """总纲：title/style/scenes/props/beats（幕表）。

    characters: 预置角色 dict 列表[{"name","prompt"}]，由调用方固定传入，LLM 不生成。
    preset_title: 可选，预置标题（如用书名号片名时）。
    minimax_mode: 启用六段式模板时为 "six_section" / "director"；否则 None。
    dialogue_ratio: 对白目标占比（0~1，如 0.6）。
    """
    char_lines = "\n".join(f"{i + 1}. {c.get('name', '')}：{c.get('prompt', '')}"
                           for i, c in enumerate(characters))
    title_json = f'"{preset_title}"' if preset_title else '"标题"'
    # 预置角色为空：要求 LLM 在总纲里自拟 2-15 个角色（替代默认 1 个主角）
    if characters:
        char_section = (
            f"本剧已确定出场角色（剧中使用，勿改动、勿增删）：\n{char_lines}\n\n"
            f"要求：\n- 故事围绕上面 {len(characters)} 个角色展开，每个角色都要有戏份；"
            f"用角色本名指代，不新增其他主角。\n"
        )
        char_json = ""
    else:
        char_section = (
            "本剧角色尚未确定：请根据故事梗概构思全剧出场角色，输出到 characters 数组"
            "（2-15 个角色，主角放第一个）。每个角色含 name（中文名）与 prompt"
            "（英文定妆提示词 15-20 词：年龄性别、脸型五官、发型发色、服饰款式颜色）与 voice（中文音色偏好 ≤8 字，例如青年女声温和，供 TTS 配音）。\n\n"
            "要求：\n- 每个角色都要在剧情中有戏份；用角色本名指代，不新增其他主角。\n"
        )
        char_json = (
            '  "characters": [\n'
            '    {"name": "主角中文名", "prompt": "英文定妆提示词（15-20词）"},\n'
            '    {"name": "配角1中文名", "prompt": "英文定妆提示词（15-20词）"},\n'
            '    {"name": "配角2中文名", "prompt": "英文定妆提示词（15-20词）"}\n'
            "  ],\n"
        )
    _genre_block = add_genre_director(genre_text)
    _art_block = add_art_style_prompt(art_text)
    _constraints = (_genre_block + _art_block).strip()
    return f"""你是短剧导演兼编剧。用户会给一句话故事梗概，你要先做全剧总纲，只输出 JSON：
{{
  "title": {title_json},
  "style": "英文全局风格（8-10词），涵盖时代场景、色调、光影、画质",
{char_json}  "scenes": {{"场景名": "该场景英文描述（15-30词），涵盖环境、氛围、光线、关键道具位置"}},
  "props": {{"物品名": "该关键物品英文描述（10-20词），涵盖外观、材质、大小、在剧情中的作用"}},
  "beats": [
    {{"scene": "本幕中文场景名（≤12字）", "brief": "英文剧情要点与运镜方向（30-40词），含本幕情绪氛围"}}
  ]
}}

{char_section}要求：
- scenes 是全部故事场景的英文描述字典；props 是贯穿剧情的关键物品（如信、法宝、手机等）英文描述字典。
- 目标总时长 {target_seconds} 秒，约 {n_shots} 个镜头（每镜约 8-15 秒）。
- 分 {n_beats} 幕（每幕 4-5 个镜头），幕数已定，不要增减。
- 每幕 brief 用英文写清：这一幕发生什么、出场角色、场景地点、关键物品、镜头重点（特写/全景/慢镜/手持等），并注明本幕的情绪基调（紧张/甜腻/悲伤/爆发等）与人物情感走向。
- 整个故事要有起承转合：开场钩子、冲突升级、转折、高潮、结局，且幕与幕、段与段之间情节要连续推进、逻辑无缝。
- beats 数组长度必须正好是 {n_beats}。
{_constraints}
{f"''' - 【对白占比——增强连贯性】成片对白口播时间必须占全片总时长 {int(round(dialogue_ratio*100))}% 以上：每幕大部分镜头都要安排有来有回、推动情节的口语化对白，避免连续静默；幕内 brief 要写明本幕台词重头戏与情绪张力。'''" if dialogue_ratio and dialogue_ratio > 0 else ""}
{f"''' - 【六段式模板】最终每镜头将改写为 MiniMax-H3 六段式提示词（主体定义/摘要/保留分析/详细描述/整体声景/非叙事配乐），本总纲需提供可复用的公共主体：角色定妆、场景描述、关键物品要具体到能逐字锁定外观，供全片共享。'''" if minimax_mode in ("six_section", "director") else ""}
{f"''' - 【dyt 工作流模板】最终每镜头将改写为 dyt.json（MiniMax H3 fl2va）的中文导演式提示词：video_prompt 必须用中文，直接以（X-Y秒）分段写出动作/运镜/情绪（如（0-3秒）…（3-6秒）…），各段时间相加等于该镜头 duration；场景/角色/物品描述要具体到能逐字锁定外观，供全片共享。每个镜头的 video_prompt 严禁少于 500 字：写足本镜完整剧情动作分解、与上一镜的衔接（无跳切、画面持续连贯）、出场人物外观锚定（脸型/发型/服饰颜色逐字沿用定妆词，不崩脸）、人物情绪与说话语气、景别运镜与光线节奏。'''" if minimax_mode == "dyt" else ""}

只输出 JSON，第一行以 {{ 开头，最后一行以 }} 结尾，不要任何其他文字、解释或代码块。
重要：输出中禁止出现任何推理、规划、词数统计、草稿或英文备注。直接从 {{ 开始写 JSON，一次成型。"""


def segment_system_prompt(title, character, style, beat, start, end, count,
                          characters=None, scenes=None, props=None, prev_end=None,
                          minimax_mode=None, dialogue_ratio=None, is_first=False,
                          genre_text="", art_text=""):
    """逐幕扩写：给定一幕信息，输出该幕的 shots 数组（含角色/场景/物品引用）。

    prev_end: 可选，上一幕/上一段最后一个镜头的画面描述（英文或中文），用于让本幕第一镜无缝衔接上一幕结尾。
    minimax_mode/dialogue_ratio/is_first: 六段式/对白占比约束。
    """
    beat_scene = beat.get("scene", "")
    beat_brief = beat.get("brief", "")
    per_shot = 11.0
    target_sec = round((end - start + 1) * per_shot)
    # 角色名列表，供镜头 character_refs 引用
    char_names = "、".join(c.get("name", "") for c in (characters or [])) or character
    scene_names = "、".join(scenes.keys()) if scenes else ""
    prop_names = "、".join(props.keys()) if props else ""
    prev_block = ""
    if prev_end:
        prev_block = (
            f"\n【上一幕/上一段结尾画面（本幕第 {start} 个镜头必须从严去衔接它）】\n{prev_end}\n"
            "本幕第 1 个镜头的 transition_prev / image_prompt / video_prompt 要明确承接上面的结尾画面，"
            "例如机位、人物位置、动作或光线从上一段末尾延续过来，做到跨幕无缝、不跳切。\n"
        )
    _genre_block = add_genre_director(genre_text)
    _art_block = add_art_style_prompt(art_text)
    _constraints = (_genre_block + _art_block).strip()
    return f"""你是短剧导演兼编剧，正在为一部长剧逐幕扩写分镜。已确定：
- 标题：{title}
- 全局风格（必须逐字使用）：{style}
- 出场角色（name，引用时用这个名字）：{char_names}
- 可用场景（name）：{scene_names or "本幕 scene 自拟"}
- 可用关键物品（name）：{prop_names or "本幕按需自拟"}

本幕信息：
- 幕名：{beat_scene}
- 本幕要点：{beat_brief}
- 本幕镜头序号：{start} 到 {end}（共 {count} 个镜头）
{prev_block}
请为这一幕输出镜头列表，只输出 JSON：
{{
  "shots": [
    {{
      "shot": {start},
      "scene": "本幕场景（≤12字，尽量从可用场景中选用）",
      "character_refs": ["本镜头出场角色名，来自上面的角色列表"],
      "scene_ref": "本镜头场景名（从上面可用场景中选）",
      "props": ["本镜头关键物品名（可为空[]）"],
      "plot": "本镜头情节与情感描写（≤40字中文）：正在发生的冲突/转折、人物心理与情绪、镜头氛围",
      "dialogue_list": [{{"speaker": "角色名（本镜出场角色；旁白/画外音留空串）", "text": "台词（≤45字，简体中文）"}}],
      "position": "画面站位（≤25字）：谁在画面左/右/中、主次与朝向，多人对话镜头必须给出",
      "video_prompt": "英文运镜提示词（≤40词），描述画面动作与镜头语言",
      "transition_prev": "衔接上一镜头的说明（≤25词英文）：从上一个镜头的什么画面/动作自然过渡到本镜头，保证分镜间动作连续、位置连贯",
      "duration": "10"
    }}
  ]
}}

硬性要求：
- 恰好 {count} 个镜头，shot 从 {start} 连续编到 {end}。
- character_refs 必须用上面给出的角色名，至少 1 个；scene_ref 从可用场景中选。
- video_prompt 末尾追加全局风格；props 仅当该镜头确实出现关键物品才填。
- duration 取 8-15 的整数字符串，**由节奏自然决定**：动作/对话推进快或静止画面用短时长（8-10），完整场景叙述/情感慢镜/大场面用长时长（12-15），本幕总秒数尽量接近 {target_sec} 秒。
- plot 和 dialogue_list 是本幕"情感与情节"的关键：dialogue_list 必须为数组（每项 speaker+text）、口语化、能推动情节、体现人物关系与冲突；plot 要把每一镜的情绪推进写具体，杜绝流水账。
- transition_prev 是"分镜衔接"关键：必须写明上一镜头尾画面怎样延续到本镜头开头（如人物从门外走进、镜头横移跟随、上一动作的连续），保证分镜之间完美衔接、位置与动作连贯不跳切。
- scene/plot/dialogue_list 中文，video_prompt/transition_prev 英文；dialogue_list 数组的 speaker 用角色名、text 用简体中文。
- 同一角色跨镜头服饰颜色必须一致（以 characters 定妆 prompt 为准，不得改写颜色）；dialogue_list 数组中的 speaker 必须与 character_refs 一致，禁止角色A台词被角色B说出。
- 不要省略逗号，不要输出代码块。
{f"''' - 【对白占比——增强连贯性】本幕及全片对白口播时间须占全片总时长 {int(round(dialogue_ratio*100))}% 以上：几乎每个镜头都要有推动情节、有来有回的口语化对白（dialogue_list 为数组），避免连续静默；dialogue_list 要与 duration 匹配，口播密集的镜可拉长、静默推进的镜要短。'''" if dialogue_ratio and dialogue_ratio > 0 else ""}
{f"''' - 【六段式模板】本镜头将改写为 MiniMax-H3 六段式提示词：video_prompt 需写清画面动作与镜头语言（供详细描述段引用），dialogue_list 为对白主体，plot 提供情绪张力，scene/scene_ref 供场景与物品标签映射，全部字段尽量具体以支撑六段式重组。video_prompt 需详尽充分：写清本镜完整剧情动作分解、与上一镜衔接（无跳切、画面持续连贯）、出场人物外观锚定（脸型/发型/服饰颜色与定妆词逐字一致，不崩脸）、人物情绪描述与说话语气、景别运镜与光线节奏（英文不少于 150 词，若用中文则不少于 500 字）。'''" if minimax_mode in ("six_section", "director") else ""}
{_DYT_SEG_NOTE if minimax_mode == "dyt" else ""}

{_constraints}

只输出 JSON，第一行以 {{ 开头，最后一行以 }} 结尾，输出最后一个 }} 后立即停止。
重要：输出中禁止出现任何推理、规划、词数统计、草稿或英文备注。直接从 {{ 开始写 JSON，一次成型。"""
  
    
  
def add_genre_director(genre):  
    # Return story-genre director-constraint text to append into generate_script system prompt.  
    if not genre:  
        return ''  
    try:  
        from factory import toonflow_skills as _tfs  
        return '\n\u3010\u6545\u4e8b\u9898\u6750\u5bfc\u6f14\u7ea6\u675f\u3011\n' + _tfs.story_genre_director_prompt(genre)  
    except Exception:  
        return ''  
  
  
def add_art_style_prompt(style):  
    # Return art-style character/shot prompt constraint text to append into generate_script system prompt.  
    if not style:  
        return ''  
    try:  
        from factory import toonflow_skills as _tfs  
        return '\n\u3010\u7f8e\u672f\u98ce\u683c\u7ea6\u675f\u3011\n' + _tfs.art_style_prompts(style)  
    except Exception:  
        return ''  
