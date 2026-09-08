# -*- coding: utf-8 -*-
"""MiniMax-H3 六段式 / 连续剧情（导演台）提示词构建模块。

把「提示词大师」的两套 MiniMax 模板工程化，应用到短剧工厂逐镜头 H3 视频生成：

1) Minimax 六段式通用提示词（Full-Reference）：
   主体定义 / 摘要 / 保留分析 / 详细描述 / 整体声景 / 非叙事配乐
   （主体定义 → 非叙事配乐，全片共享公共主体定义，锁角色/场景/物品外观）

2) 连续剧情（导演台）：跨镜头/跨幕加「无硬切。紧接上一段。」与稳定收尾手势，
   保证分镜动作连续、位置连贯、不跳切，增强视频连贯性与一致性。

本模块把剧本的 script.json（characters/scenes/props/style + 逐镜 shots）重组为
符合上述格式的单镜头 H3 prompt 文本。技术标记（<Subject N> / <Picture N> /
fully_preserved / [Shot N] At MM:SS.mmm / <d>[Chinese]…</d>）保持英文格式，
六段标题用中文。

参考图绑定：refs dict 由调用方（generator.build_shot_video_prompt）传入，
把角色/场景/物品映射到 <Picture N>，本模块据此在「主体定义」与「详细描述」
中嵌入图片标签，让 H3 模型知道用哪几张参考图。
"""
import os
import re

# 六段标题（中文，模板强制）
SECTIONS = ("主体定义", "摘要", "保留分析", "详细描述", "整体声景", "非叙事配乐")

# 视觉保留关系标记
_PRESERVED = "fully_preserved"
_PARTIAL = "partially_preserved"
_WEAK = "weak_reference"


def _tag_map(script):
    """生成 <Subject N> 与实体名 的映射，供正文引用。

    返回 (subject_map, next_subject)：
      subject_map: {实体内核(key) -> "<Subject N>"}，key 见 _entity_key
      next_subject: 下一个可用 Subject 序号（1-based）
    角色按 characters 顺序，场景按 scenes，物品按 props。
    """
    subject_map = {}
    n = 1
    for c in script.get("characters") or []:
        subject_map[_entity_key("char", c.get("name", ""))] = f"<Subject {n}>"
        n += 1
    for sc in (script.get("scenes") or {}):
        subject_map[_entity_key("scene", sc)] = f"<Subject {n}>"
        n += 1
    for pr in (script.get("props") or {}):
        subject_map[_entity_key("prop", pr)] = f"<Subject {n}>"
        n += 1
    return subject_map, n


def _entity_key(kind, name):
    return f"{kind}:{str(name or '').strip()}"


def _resolve_subject(shot, kind, name, subject_map):
    """根据镜头引用解析某个实体对应的 <Subject N>。找不到返回 None。"""
    if kind == "char":
        # 角色：按名字匹配 subject_map 中已注册的 char key
        for key, tag in subject_map.items():
            if key.startswith("char:") and (key == f"char:{name}" or key[5:] in name or name in key[5:]):
                return tag
        return None
    return subject_map.get(_entity_key(kind, name or "")) or subject_map.get(_entity_key(kind, str(name or "").strip()))


def _pic_for(shot, refs, kind, name=None):
    """从 refs 拿到某实体绑定到的 <Picture N> 标签。

    refs 结构：{"character": "<Picture 1>", "scene": "<Picture 2>", "prop_<name>": "<Picture 3>"}
    返回 <Picture N> 或 None。
    """
    if not refs:
        return None
    if kind == "char":
        if name and refs.get("char_" + name):
            return refs["char_" + name]
        if name:
            for k, v in refs.items():
                if k.startswith("char_") and (name in k[5:] or k[5:] in name):
                    return v
        return refs.get("character")
    if kind == "scene":
        return refs.get("scene")
    if kind == "prop":
        return refs.get(f"prop_{name}")
    return None


def _build_subject_definitions(script, subject_map, refs, shot):
    """构建「主体定义」段：全片公共，一次锁定角色/场景/物品外观。

    每行一条：<Subject N> 是 <Picture N> 中的…… 身份与穿着完全锁定参考图。
    """
    lines = []
    # 角色
    for c in script.get("characters") or []:
        name = c.get("name", "")
        tag = subject_map.get(_entity_key("char", name))
        if not tag:
            continue
        pic = _pic_for(shot, refs, "char", name)
        prompt = (c.get("prompt") or "").strip()
        base = f"{tag} 是" + (f" {pic} 中的" if pic else " ")
        # 用角色定妆提示词的中文化概要做一句锁定（保留英文关键词供模型理解）
        detail = f"身份与穿着完全锁定参考图：{prompt}" if pic else f"全剧唯一外观设定：{prompt}"
        lines.append(f"{base}{name}，{detail}")
    # 场景
    for sc_name, sc_desc in (script.get("scenes") or {}).items():
        tag = subject_map.get(_entity_key("scene", sc_name))
        if not tag:
            continue
        pic = _pic_for(shot, refs, "scene", sc_name)
        base = f"{tag} 是" + (f" {pic} 中的" if pic else " ")
        lines.append(f"{base}场景「{sc_name}」，外观与氛围锁定参考图：{sc_desc}")
    # 物品
    for pr_name, pr_desc in (script.get("props") or {}).items():
        tag = subject_map.get(_entity_key("prop", pr_name))
        if not tag:
            continue
        pic = _pic_for(shot, refs, "prop", pr_name)
        base = f"{tag} 是" + (f" {pic} 中的" if pic else " ")
        lines.append(f"{base}关键物品「{pr_name}」，外观与作用锁定参考图：{pr_desc}")
    return "\n".join(lines) if lines else "本镜头无可复用可见内容单元。"


def _build_summary(script, shot, shot_idx, total):
    """构建「摘要」段：本镜头任务类型 + 目标 + 主要参考关系。"""
    dialogue = dialogue_to_prompt_text(shot)
    scene = shot.get("scene") or shot.get("scene_ref") or ""
    plot = (shot.get("plot") or "").strip()
    head = f"[reference generation] 第 {shot_idx}/{total} 镜头"
    parts = [head]
    if scene:
        parts.append(f"场景「{scene}」")
    if plot:
        parts.append(f"情节：{plot}")
    if dialogue:
        parts.append(f"含对白「{dialogue}」")
    parts.append("以参考图锁定人物/场景/物品一致性")
    return "，".join(parts) + "。"


def _build_retention(shot, script, subject_map, refs, shot_idx):
    """构建「保留分析」段：说明各参考内容如何保留/迁移。"""
    lines = []
    chars_in = shot.get("character_refs") or shot.get("characters") or []
    for cname in chars_in:
        tag = _resolve_subject(shot, "char", cname, subject_map)
        pic = _pic_for(shot, refs, "char", cname)
        if tag:
            loc = f"({pic} in [Shot {shot_idx}] )" if pic else f"([Shot {shot_idx}] )"
            lines.append(f"{tag} {loc}: {_PRESERVED} - 外观、穿着、发型与神态完整保留，沿用主体定义。")
    # 场景
    sc = shot.get("scene_ref") or shot.get("scene")
    if sc:
        tag = _resolve_subject(shot, "scene", sc, subject_map)
        pic = _pic_for(shot, refs, "scene", sc)
        if tag:
            loc = f"({pic} in [Shot {shot_idx}] )" if pic else f"([Shot {shot_idx}] )"
            lines.append(f"{tag} {loc}: {_PRESERVED} - 环境、光线与关键道具位置沿用主体定义。")
    # 物品
    for p in shot.get("props") or []:
        pname = p if isinstance(p, str) else (p.get("name") or "")
        tag = _resolve_subject(shot, "prop", pname, subject_map)
        pic = _pic_for(shot, refs, "prop", pname)
        if tag:
            loc = f"({pic} in [Shot {shot_idx}] )" if pic else f"([Shot {shot_idx}] )"
            lines.append(f"{tag} {loc}: {_PRESERVED} - 关键物品外观与作用沿用主体定义。")
    return "\n".join(lines) if lines else f"[Shot {shot_idx}] 本镜头以参考图为主体视觉锚点，全部 {_PRESERVED}。"


def _build_detail(shot, script, subject_map, refs, shot_idx, params):
    """构建「详细描述」段：按播放顺序写画面/动作/镜头/声音/对白。

    shot>=2 且不是独立起拍时，开头加「无硬切。紧接上一段。」（连续剧情导演台）。
    """
    lines = []
    dialogue = dialogue_to_prompt_text(shot)
    plot = (shot.get("plot") or "").strip()
    video = (shot.get("video_prompt") or "").strip()
    transition = (shot.get("transition_prev") or "").strip()
    style = (script.get("style") or "").strip()
    scene = shot.get("scene") or shot.get("scene_ref") or ""

    is_first = bool(params.get("is_first"))
    if not is_first:
        lines.append("无硬切。紧接上一段。")

    if scene:
        lines.append(f"场景「{scene}」；{scene} 沿用主体定义的环境与光线。")
    pos = (shot.get("position") or "").strip()
    if pos:
        lines.append(f"画面站位：{pos}。")
    if plot:
        lines.append(f"情节与情绪：{plot}。")
    if video:
        lines.append(f"[Shot {shot_idx}] At 00:00.000, {video}。")
    if style:
        lines.append(f"全局风格：{style}。")
    if transition:
        lines.append(f"承接上一镜：{transition}。")
    if dialogue:
        dlg_lines = _dialogue_block(shot, script, refs)
        if dlg_lines:
            lines.append(dlg_lines)
        else:
            lines.append(f"对白：<d>[Chinese] {_lock_language(dialogue)}</d>")
    else:
        lines.append("本镜头无对白，以动作/环境声推进。")
    return "\n".join(lines)


def _build_soundscape(shot, script, params):
    """构建「整体声景」段：总结全程环境音与物理声。"""
    dialogue = dialogue_to_prompt_text(shot)
    if dialogue:
        return f"贯穿全镜头的环境底噪与空间感；人声对白清晰前置，其余环境音作为背景衬底，保证口播占主导。"
    scene = shot.get("scene") or shot.get("scene_ref") or ""
    return f"「{scene}」的自然环境音与物理声贯穿本镜头，空间感与层次连续，无对白。"


def _build_music(script, params):
    """构建「非叙事配乐」段：描述仅观众听见的背景音乐。"""
    motif = (script.get("music_motif") or "").strip()
    if motif:
        return f"配乐沿用全片统一动机：{motif}。跨镜头不断档，结尾轻收束。"
    return "统一且克制的氛围配乐，贯穿全片不中断，跨镜头不断档，结尾轻收束。"


def build_six_section_prompt(shot, script, refs, params):
    """把一个镜头重组为 MiniMax-H3 Full-Reference 六段式提示词。

    返回：六段式中文标题 + 中文正文的完整 prompt 文本（可直接作为 H3 节点 prompt）。
    params 至少含：
      shot_idx      : 镜头序号（1-based）
      total         : 总镜头数
      is_first      : 是否首个镜头（决定是否加「无硬切。紧接上一段。」）
      dialogue_ratio: 对白目标占比（0~1，如 0.6），用于在提示中强调对白密度
    """
    shot_idx = int(params.get("shot_idx", 1))
    total = int(params.get("total", 1))
    dialogue_ratio = float(params.get("dialogue_ratio", 0.6) or 0.6)

    subject_map, _ = _tag_map(script)
    s_def = _build_subject_definitions(script, subject_map, refs, shot)
    s_sum = _build_summary(script, shot, shot_idx, total)
    s_ret = _build_retention(shot, script, subject_map, refs, shot_idx)
    s_det = _build_detail(shot, script, subject_map, refs, shot_idx, params)
    s_snd = _build_soundscape(shot, script, params)
    s_mus = _build_music(script, params)

    # 对白占比强调：注入到摘要/详细描述，促使模型把口播做足
    if dialogue_ratio and dialogue_ratio > 0:
        target_pct = int(round(dialogue_ratio * 100))
        s_sum += f" 对白需覆盖本镜头 {target_pct}% 以上时长，口播密集、情感饱满。"
        if not dialogue_to_prompt_text(shot):
            s_det += f"\n注意：本镜头应补足对白，使口播占时 ≥{target_pct}%，保证剧情连贯通顺。"

    prompt = (
        f"{SECTIONS[0]}:\n{s_def}\n\n"
        f"{SECTIONS[1]}:\n{s_sum}\n\n"
        f"{SECTIONS[2]}:\n{s_ret}\n\n"
        f"{SECTIONS[3]}:\n{s_det}\n\n"
        f"{SECTIONS[4]}:\n{s_snd}\n\n"
        f"{SECTIONS[5]}:\n{s_mus}"
    )
    return prompt


# ============================================================
# 对白占比（dialogue ≥ 60%）校验工具
# ============================================================
def dialogue_seconds(shot):
    """估算一个镜头内对白口播秒数。

    以每字约 0.28s 口播速率、结合 duration 上限估算，供占比校验。
    """
    dur = float(str(shot.get("duration_sec") or shot.get("duration") or 5).strip() or 5)
    items = norm_dialogue(shot)
    total_chars = sum(len(it.get("text") or "") for it in items)
    if total_chars <= 0:
        return 0.0
    # 中文口语约 4 字/秒
    secs = max(0.5, total_chars / 4.0)
    return min(secs, dur)


def dialogue_ratio(script):
    """计算全片对白口播总秒数 / 视频总秒数，返回 (ratio, dialogue_sec, total_sec)。"""
    shots = script.get("shots") or []
    total_sec = 0.0
    dlg_sec = 0.0
    for s in shots:
        dur = float(str(s.get("duration_sec") or s.get("duration") or 5).strip() or 5)
        total_sec += dur
        dlg_sec += dialogue_seconds(s)
    if total_sec <= 0:
        return 0.0, dlg_sec, total_sec
    return dlg_sec / total_sec, dlg_sec, total_sec


def validate_dialogue_ratio(script, target=0.6, log=None):
    """校验全片对白占比是否达标；不达标则提示并给出补足建议。

    自动补足策略：对占比不足的镜头，把 duration 相应缩短，让对白口播相对更密集；
    但更稳妥的做法是只提示用户，避免擅自改节奏。这里返回 (ok, ratio, message)。
    """
    ratio, dlg_sec, total_sec = dialogue_ratio(script)
    target_pct = int(round(target * 100))
    if ratio >= target:
        return True, ratio, f"对白占比达标：{ratio*100:.0f}%（目标≥{target_pct}%）"
    # 提示 + 给出可用的补足建议
    deficit = target - ratio
    need_dlg = dlg_sec + deficit * total_sec
    msg = (f"对白占比不足：当前 {ratio*100:.0f}%（{dlg_sec:.0f}s/{total_sec:.0f}s，目标≥{target_pct}%）。"
           f"建议给对白偏少的镜头补足口语化台词，或缩短静默镜头时长，使对白口播达到约 {need_dlg:.0f}s 即可达标。")
    if log:
        log(msg)
    return False, ratio, msg


# ============================================================
# dyt.json 工作流提示词模板（中文导演式 + 图N参考 + （X-Y秒）时段）
# ============================================================
# ============================================================
# dyt 导演台增强：语言锁定 / 定妆锁定 / 站位 / 说话人绑定
# ============================================================


def _lock_language(text):
    """把对白文本锁定为简体中文：过滤英文/其他语言字母，仅保留中文与常用标点。"""
    if not text:
        return text
    out = []
    for ch in text:
        if '\u4e00' <= ch <= '\u9fff':
            out.append(ch)
        elif ch in '，。！？、；：""''（）…—·～《》〈〉0123456789 ':
            out.append(ch)
        elif ch in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ':
            continue  # 过滤英文
        elif '\uff00' <= ch <= '\uffef' or '\u3000' <= ch <= '\u303f':
            out.append(ch)
        else:
            out.append(ch)
    return ''.join(out).strip()


def _clean_dlg_text(s):
    """清理对白文本脏字符：\r、全角空格、行首尾空白、多余空行。"""
    s = (s or "").replace("\r", "").replace("\u3000", " ").strip()
    lines = [ln.strip() for ln in s.split("\n") if ln.strip()]
    return "\n".join(lines) if len(lines) > 1 else (lines[0] if lines else "")


_DLG_SPK_RE = re.compile(r"^([\u4e00-\u9fffA-Za-z0-9_·\-]{1,16})\s*[：:]\s*(.*)$")


def _text_to_dialogue(text):
    """旧字符串格式（"林晚：台词\n阿杰：…"）拆成 [{"speaker","text"}]；无前缀的整行为旁白。"""
    out = []
    for raw in _clean_dlg_text(text).split("\n"):
        line = raw.strip()
        if not line:
            continue
        m = _DLG_SPK_RE.match(line)
        if m and m.group(2).strip():
            out.append({"speaker": m.group(1).strip(), "text": m.group(2).strip()})
        else:
            out.append({"speaker": "", "text": line})
    return out


def norm_dialogue(dlg):
    """把 dialogue 归一化为 [{"speaker": 角色名或"", "text": 台词}] 列表。

    兼容多种输入：
    - shot dict：自动取 dialogue_list（新字段名）优先、dialogue（旧字段名）回退
    - 字符串（旧格式）："林晚：你等等！\n阿杰：……"
    - 数组（新格式）：[{"speaker": "林晚", "text": "你等等！"}, ...]
    顺带清理换行/缩进/全角空格等脏字符；空对话返回 []。
    """
    if dlg is None:
        return []
    if isinstance(dlg, dict):
        # shot dict：dialogue_list 优先，回退旧字段 dialogue
        v = dlg.get("dialogue_list")
        dlg = v if v is not None else dlg.get("dialogue")
    if dlg is None:
        return []
    if isinstance(dlg, list):
        out = []
        for it in dlg:
            if isinstance(it, str):
                out.extend(_text_to_dialogue(it))
            elif isinstance(it, dict):
                spk = str(it.get("speaker") or "").strip()
                txt = _clean_dlg_text(it.get("text"))
                if txt:
                    out.append({"speaker": spk, "text": txt})
        return out
    return _text_to_dialogue(dlg)


def dialogue_has_speaker(dlg):
    """dialogue 中是否有显式说话人（speaker 非空）。"""
    return any((it.get("speaker") or "").strip() for it in norm_dialogue(dlg))


def dialogue_to_prompt_text(dlg):
    """把 dialogue 转回用于拼接进 H3 提示词的文本（"角色名：台词" 每行一条；旁白无前缀）。"""
    items = norm_dialogue(dlg)
    if not items:
        return ""
    parts = []
    for it in items:
        spk = (it.get("speaker") or "").strip()
        txt = (it.get("text") or "").strip()
        parts.append((spk + "：" + txt) if spk else txt)
    return "\n".join(p for p in parts if p)


def _split_dialogue(dialogue, char_names=None):
    """把 dialogue（字符串或结构化数组）拆成 [(说话人或None, 台词), ...]。

    char_names: 已知角色名集合。命中名字的 speaker 作为说话人；
    未命名的 speaker 视为台词的普通文本（避免把 "他说" 误判为说话人）。
    speaker 为空/未知时视为旁白（或沿用前一句说话人）。
    """
    names = set(char_names or [])
    segs = []
    pending = None  # 当前说话人
    for item in norm_dialogue(dialogue):
        spk = (item.get("speaker") or "").strip()
        txt = (item.get("text") or "").strip()
        if not txt:
            continue
        if spk and (not names or spk in names):
            segs.append((spk, txt))
            pending = spk
        else:
            # 未知说话人：把"名字："前缀拼回台词文本，作为普通文本保留
            segs.append((pending, (spk + "：" + txt) if spk else txt))
    return segs





def _char_pic_tag(refs, cname):
    """按角色名反查 <Picture N>：优先 char_<名>，其次 character（首角色）。"""
    if not refs:
        return None
    if cname and refs.get("char_" + cname):
        return refs["char_" + cname]
    if cname:
        for k, v in refs.items():
            if k.startswith("char_") and (cname in k[5:] or k[5:] in cname):
                return v
    return refs.get("character")


def _shot_chars(shot, script):
    """本镜头出场角色名列表（优先 character_refs / characters，其次从对白说话人推断）。"""
    refs_list = shot.get("character_refs") or shot.get("characters") or []
    out = [str(x) for x in refs_list if x]
    if not out:
        for spk, _ in _split_dialogue(shot):
            if spk and spk not in out:
                out.append(spk)
    return out


def _dialogue_block(shot, script, refs):
    """生成「对白」段：逐句绑定唯一说话人 → 图N，中文语言锁定 <d>[Chinese]。

    双人对白时明确每句台词的发起者：说话人开口时镜头聚焦该角色、嘴型同步，
    其他角色保持闭嘴倾听；严禁把某角色的台词由画面中另一角色说出。
    """
    dlg = dialogue_to_prompt_text(shot)
    if not dlg:
        return ""
    char_names = [c.get("name", "") for c in (script.get("characters") or [])]
    segs = _split_dialogue(dlg, char_names)
    if not segs:
        return ""
    # 单角色镜头：无前缀的台词视为该角色所说（避免被标成旁白）
    shot_chars = _shot_chars(shot, script)
    default_spk = shot_chars[0] if len(shot_chars) == 1 else None
    multi = len(shot_chars) > 1 or len({s for s, _ in segs if s}) > 1
    if multi:
        header = ("对白（双人对话。每句台词必须由【说话人】本人清晰说出，发音与口型属于且仅属于该说话人；"
                  "说话人开口时镜头聚焦该角色，其他角色保持闭嘴倾听，严禁把某角色的台词由画面中另一角色说出。"
                  "全程简体中文普通话，禁止夹杂英文或其他语言）：")
    else:
        header = "对白（请逐句由指定角色清晰说出，全程简体中文普通话，禁止夹杂英文或其他语言）："
    lines = [header]
    prev_spk = None
    for spk, text in segs:
        text = _lock_language(text)
        if not text:
            continue
        if not spk and default_spk:
            spk = default_spk
        if spk:
            pic = _char_pic_tag(refs, spk)
            loc = ("（" + pic + " 中的" + spk + "）") if pic else ("（" + spk + "）")
            if multi and prev_spk and prev_spk != spk:
                lines.append("说话人切换为" + loc + "。")
            # 说话人标注放在 <d> 标签外（仅作导演指令，H3 原生音频不会读出"本人说"等字样）；
            # 标签内仅保留台词本身，避免语音开头多出"本人说"。
            lines.append('本句由' + loc + '说出：<d>[Chinese] "' + text + '"。 </d>')
            prev_spk = spk
        else:
            lines.append("<d>[Chinese] （旁白）" + text + "</d>")
    if len(lines) <= 1:
        return ""
    return "\n".join(lines)
def _cast_block(shot, script, refs):
    """生成「人物定妆」段：本镜头出场角色逐字锁定参考图 + 英文定妆（含服饰颜色）。"""
    chars = script.get("characters") or []
    names = _shot_chars(shot, script)
    lines = ["人物定妆锁定（本镜头出场角色外观必须与对应参考图完全一致，服饰颜色、款式、发型不得改变）："]
    any_line = False
    for c in chars:
        cname = c.get("name", "")
        if names and cname not in names:
            continue
        prompt = (c.get("prompt") or "").strip()
        pic = _char_pic_tag(refs, cname)
        if pic:
            lines.append("- " + pic + " = " + cname + "：" + (prompt or "（以参考图为准）") +
                         "（外观完全锁定参考图，不变形不变色）")
        elif prompt:
            lines.append("- " + cname + "：" + prompt + "（外观全剧唯一设定，保持不变）")
        else:
            continue
        any_line = True
    if not any_line:
        return ""
    return "\n".join(lines)


def _position_block(shot, script):
    """生成「画面站位」段：明确各角色在画面中的左右位置与构图，避免站位错乱。"""
    names = _shot_chars(shot, script)
    if not names:
        return ""
    if len(names) == 1:
        return "画面站位：" + names[0] + " 位于画面中心，人物面部朝向镜头，占据画面主体；站位稳定不漂移。"
    left = names[0]
    right = names[-1]
    mid = names[1:-1]
    extra = "，" + "、".join(mid) + " 居中或随镜头自然入画" if mid else ""
    return ("画面站位：" + left + " 位于画面左侧，" + right + " 位于画面右侧，两人相对而视或侧身交流"
            + extra + "；站位在整段视频中保持不变，不得左右互换、不得离开画面。")


def _audio_block(shot, script, tts_mode=False):
    """生成「整体声景」段：官方 dyt.json（H3）原生音频——环境声/音效/人声一体生成。

    tts_mode=True 时（外部 TTS 配音接管人声），提示 H3 弱化人声/只作环境底噪，
    避免与 TTS 人声冲突形成双声。
    """
    dlg = dialogue_to_prompt_text(shot)
    scene = shot.get("scene") or shot.get("scene_ref") or ""
    if tts_mode:
        if dlg:
            base = ("声音：" + scene + " 的环境底噪与音效作为背景衬底（音量低、不抢戏），"
                    "不要生成或突出人声对白（人声将由外部配音后期替换），嘴型动作保持自然。")
        else:
            base = "声音：" + scene + " 的环境音与物理声贯穿全镜头（如风声、脚步声、器物声），无对白。"
    elif dlg:
        base = "声音：" + scene + " 的环境底噪作为背景衬底，人声对白清晰前置、占据主导，嘴型与台词同步。"
    else:
        base = "声音：" + scene + " 的环境音与物理声贯穿全镜头（如风声、脚步声、器物声），无对白。"
    return base + "音效与配乐保持连续不突兀，音画同步。"

def _pic_num(refs, kind, name=None):
    """从 refs 反查某实体绑定的 <Picture N> 序号（int，1-based）；无则 None。

    refs 例：{"character": "<Picture 1>", "scene": "<Picture 2>", "prop_剑": "<Picture 3>"}
    """
    if not refs:
        return None
    tag = None
    if kind == "char":
        tag = refs.get("character")
    elif kind == "scene":
        tag = refs.get("scene")
    elif kind == "prop":
        tag = refs.get(f"prop_{name}")
    if not tag:
        return None
    m = re.search(r"Picture\s+(\d+)", str(tag))
    return int(m.group(1)) if m else None


def _segment_text(text, duration):
    """把一段正文切成 (X-Y秒) 时段。若正文已含（X-Y秒）标记则原样返回。

    duration: 镜头秒数。切分数量 n = clamp(round(dur/5), 2, 3)。
    按句子边界（。！？；….;;!?）切句，均分到各时段，标签用（X-Y秒）。
    """
    text = (text or "").strip()
    if not text:
        return ""
    if "（" in text and "秒）" in text:
        return text
    dur = max(4.0, float(duration or 5.0))
    n = max(2, min(3, int(round(dur / 5.0))))
    # 拆句
    sentences = re.split(r"(?<=[。！？；!?;])", text)
    sentences = [s.strip() for s in sentences if s and s.strip()]
    if not sentences:
        return text
    # 句子数不足 n：按字符长度均分文本，保证每个时段都有内容
    if len(sentences) < n:
        total = len(text)
        parts = []
        start = 0
        for i in range(n):
            end = (i + 1) * total // n
            seg = text[start:end].strip()
            start = end
            if seg:
                t0 = round(dur * i / n)
                t1 = round(dur * (i + 1) / n)
                parts.append(f"（{t0}-{t1}秒）{seg}")
        return "\n".join(parts)
    # 均分句子到 n 段
    segs = [[] for _ in range(n)]
    for i, s in enumerate(sentences):
        segs[i % n].append(s)
    # 按实际时长均分时间区间
    parts = []
    for i, seg in enumerate(segs):
        if not seg:
            continue
        t0 = round(dur * i / n)
        t1 = round(dur * (i + 1) / n)
        parts.append(f"（{t0}-{t1}秒）{''.join(seg)}")
    return "\n".join(parts)


def build_dyt_shot_prompt(shot, script, refs, ref_images=None, duration=None, tts_mode=False):
    """把一个镜头组装为 dyt.json（MiniMax H3 ref2va）工作流的提示词文本。

    结构（对齐官方 dyt.json 说明与 MiniMax H3 导演台规范）：
      1) 镜头设定：场景 + 整体视觉风格（中文导演式）
      2) 图N参考说明：按连接顺序 图1=首帧/角色，图2=场景……（官方要求标签精确对应）
      3) 人物定妆锁定：逐字锁定出场角色外观与服饰颜色（参考图 + 英文定妆词）
      4) 画面站位：明确各角色左右/主次位置，避免站位错乱
      5) （X-Y秒）时段正文：动作/运镜/情绪分段，必要时标注 图N 参考
      6) 对白：逐句绑定说话人 → 图N，<d>[Chinese] 语言锁定
      7) 整体声景：环境声/音效/人声一体生成（H3 原生音频）

    若 LLM 已按 dyt 时段格式写 video_prompt（含（X-Y秒）），直接使用；
    否则用 video_prompt/plot/transition 组合文本按镜头时长自动切分时段。
    """
    dur = duration
    if dur is None:
        dur = float(str(shot.get("duration_sec") or shot.get("duration") or 5).strip() or 5)
    scene = (shot.get("scene") or shot.get("scene_ref") or "").strip()
    style = ((script or {}).get("style") or "").strip()
    plot = (shot.get("plot") or "").strip()
    dialogue = dialogue_to_prompt_text(shot)
    video = (shot.get("video_prompt") or "").strip()
    transition = (shot.get("transition_prev") or "").strip()

    # 图N 参考说明（图1 = 首帧；后续图依次为场景/物品参考）——官方要求标签精确对应
    n_refs = len(ref_images or [])
    if n_refs <= 0:
        pic_note = "本镜头无参考图，纯文生视频。"
    else:
        pic_note = "图1是视频的首帧"
        if n_refs >= 2:
            pic_note += "，图2保持场景与整体风格一致"
        if n_refs >= 3:
            pic_note += "，图3保持关键物品外观一致"
        pic_note += "。全程以对应参考图锁定人物身份、服饰颜色、场景与物品外观，禁止自行改动。"

    # 时段正文：LLM 已写时段格式则直接用，否则自动切分
    if "（" in video and "秒）" in video:
        body = video
    else:
        combo = " ".join(x for x in (video, plot, transition) if x)
        body = _segment_text(combo, dur)

    lines = []
    if scene:
        head = scene if scene.endswith(("。", "；")) else scene + "。"
        lines.append(head)
    if style:
        lines.append("整体视觉风格：" + style + "。")
    lines.append(pic_note)
    cast = _cast_block(shot, script, refs)
    if cast:
        lines.append(cast)
    pos = _position_block(shot, script)
    if pos:
        lines.append(pos)
    if body:
        lines.append(body)
    dlg_block = _dialogue_block(shot, script, refs)
    if dlg_block:
        lines.append(dlg_block)
    else:
        lines.append("本镜头无对白。")
    lines.append(_audio_block(shot, script, tts_mode=tts_mode))
    # 语言与画质硬性约束（兜底）
    lines.append("全片简体中文普通话，吐字清晰，禁止出现英文、拼音或其他语言文字；保持无字幕、无水印。")
    return "\n".join(lines)


