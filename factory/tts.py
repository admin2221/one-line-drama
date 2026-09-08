# -*- coding: utf-8 -*-
"""TTS 配音模块：edge-tts 合成 + 角色音色映射 + 对白时间轴 + ffmpeg 混音。

设计目标（角色音色一致性）：
- 每个角色绑定一个固定的 edge-tts 音色（ShortName），整部剧所有镜头该角色
  的对白都由同一个音色合成，保证音色完全一致。
- 音色来源优先级：shot/角色 voice 字段（LLM 或用户指定）-> --voice-map 覆盖
  -> 按角色性别/年龄自动映射默认音色。
- 混音策略：TTS 人声叠加在 H3 原生音频（环境音）之上，保留氛围音效。
  对白时间轴按镜头内说话人顺序 + 字数比例分配，避免超出镜头时长。

用法（在 drama_factory 中）：
    from factory import tts as tts_mod
    tts_mod.synthesize_script(script, shots_dir, output_dir, voice_map=None,
                              ffmpeg=concat.find_ffmpeg(), log=print)
"""
import asyncio
import os
import re
import subprocess
import sys

# ---------------------------------------------------------------
# 角色 -> edge-tts 音色映射表（zh-CN 中文音色，同一 ShortName 音色确定）
# ---------------------------------------------------------------
# 女声：晓晓(温和女声) / 晓伊(年轻女声) / 晓北(东北女声)
# 男声：云希(阳光男声) / 云健(沉稳男声) / 云扬(新闻男声) / 云夏(童声男声)
DEFAULT_VOICES = [
    "zh-CN-XiaoxiaoNeural",   # 晓晓：温和知性女声（主角女首选）
    "zh-CN-YunxiNeural",      # 云希：阳光青年男声（主角男首选）
    "zh-CN-YunjianNeural",    # 云健：沉稳男声（中年男/反派）
    "zh-CN-XiaoyiNeural",     # 晓伊：灵动年轻女声（少女/次要女）
    "zh-CN-YunyangNeural",    # 云扬：宽厚男声
    "zh-CN-YunxiaNeural",     # 云夏：少年感男声
    "zh-CN-liaoning-XiaobeiNeural",  # 小北：东北女声（方言感）
    "zh-CN-shaanxi-XiaoniNeural",    # 晓妮：陕西女声（方言感）
]

FEMALE_VOICES = ["zh-CN-XiaoxiaoNeural", "zh-CN-XiaoyiNeural",
                 "zh-CN-liaoning-XiaobeiNeural", "zh-CN-shaanxi-XiaoniNeural"]
MALE_VOICES = ["zh-CN-YunxiNeural", "zh-CN-YunjianNeural",
               "zh-CN-YunyangNeural", "zh-CN-YunxiaNeural"]

# 用户可在此显式绑定角色 -> 音色（也可通过 --voice-map 传）
USER_VOICE_MAP = {
    # "林晚": "zh-CN-XiaoxiaoNeural",
    # "猫老大": "zh-CN-YunxiNeural",
    # "王总": "zh-CN-YunjianNeural",
}


def _pick_voice(role_name, role, voice_map=None):
    """为一个角色选择音色 ShortName。优先级：
    1) voice_map 显式指定（--voice-map / USER_VOICE_MAP）
    2) 角色 voice 字段（LLM 输出或预置角色 JSON）
    3) 按角色 prompt/voice 中的性别关键词自动分配（默认轮转）
    返回 None 表示该角色无音色（跳过合成）。
    """
    name = (role_name or "").strip()
    if not name:
        return None
    vmap = dict(USER_VOICE_MAP or {})
    if voice_map:
        vmap.update(voice_map)
    # 1) 显式映射
    if name in vmap and vmap[name]:
        return vmap[name]
    # 2) 角色字段 voice / voice_hint
    role = role or {}
    for k in ("voice", "voice_hint", "voice_name"):
        v = role.get(k)
        if v and isinstance(v, str) and v.strip():
            v = v.strip()
            # 允许直接给 ShortName，或中文/英文音色关键词
            if v.startswith("zh-"):
                return v
            hit = _match_voice_name(v)
            if hit:
                return hit
    # 3) 自动：按角色 prompt 中性别/年龄关键词
    return _auto_voice(role)


def _match_voice_name(keyword):
    """按关键词（中文/英文）匹配音色 ShortName。"""
    kw = (keyword or "").lower()
    if not kw:
        return None
    alias = {
        "xiaoxiao": "zh-CN-XiaoxiaoNeural", "晓晓": "zh-CN-XiaoxiaoNeural",
        "xiaoyi": "zh-CN-XiaoyiNeural", "晓伊": "zh-CN-XiaoyiNeural",
        "yunxi": "zh-CN-YunxiNeural", "云希": "zh-CN-YunxiNeural",
        "yunjian": "zh-CN-YunjianNeural", "云健": "zh-CN-YunjianNeural",
        "yunyang": "zh-CN-YunyangNeural", "云扬": "zh-CN-YunyangNeural",
        "yunxia": "zh-CN-YunxiaNeural", "云夏": "zh-CN-YunxiaNeural",
        "xiaobei": "zh-CN-liaoning-XiaobeiNeural", "小北": "zh-CN-liaoning-XiaobeiNeural",
        "xiaoni": "zh-CN-shaanxi-XiaoniNeural", "晓妮": "zh-CN-shaanxi-XiaoniNeural",
    }
    for k, v in alias.items():
        if k in kw:
            return v
    # 模糊：音色名包含关键词
    for v in DEFAULT_VOICES:
        if kw in v.lower() or kw in v.split("-")[2]:
            return v
    return None


def _auto_voice(role):
    """按角色 prompt/voice 文本推断性别年龄，自动分配音色（稳定轮转）。"""
    prompt = " ".join(str(role.get(k) or "") for k in ("prompt", "voice", "voice_hint"))
    p = prompt.lower()
    # 明确性别词优先（"女声/男声/女/男"），避免年龄词（"青年"）干扰
    has_female = any((k in p) for k in ("女声", "女音", "女"))
    has_male = any((k in p) for k in ("男声", "男音", "男"))
    if not (has_female or has_male):
        # 英文性别词（注意用完整词匹配，避免 "woman" 命中 "man" 之类子串误判）
        has_female = any(k in p for k in ("female", " woman", "girl", "lady", "she",
                                          "her", "女", "女孩", "少女", "女子", "姐姐", "妈妈"))
        has_male = any(k in p for k in ("male", " man", "boy", "gentleman", "he ",
                                        "him", "男", "男孩", "青年", "男人", "哥哥", "爸爸"))
    is_female, is_male = has_female, has_male
    # 角色名可能含性别暗示
    name = str(role.get("name") or "")
    if any(k in name for k in ("妈", "姐", "妹", "娜", "丽", "玲", "芳", "娟")):
        is_female = True
    if any(k in name for k in ("爸", "哥", "弟", "叔", "伯", "总", "郎", "老", "爷")):
        is_male = True
    # 稳定分配：以角色名为种子轮转，保证每次运行同一角色同一音色
    idx = (sum(ord(c) for c in str(role.get("name") or "角色")) % 1000)
    if is_female and not is_male:
        return FEMALE_VOICES[idx % len(FEMALE_VOICES)]
    if is_male and not is_female:
        return MALE_VOICES[idx % len(MALE_VOICES)]
    return DEFAULT_VOICES[idx % len(DEFAULT_VOICES)]


# ---------------------------------------------------------------
# 对白拆分与时间轴
# ---------------------------------------------------------------
# 说话人前缀："林晚：" / "猫老大："（行首或句首，1-8 个汉字）
_SPK_RE = re.compile(r"(?:^|[\n，,。！？;；!?])\s*([\u4e00-\u9fff]{1,8})\s*[：:]")


def _split_shot_dialogue(shot, default_spk=None):
    """把镜头 dialogue 拆成 [(说话人, 台词), ...]。

    有 "角色名：" 前缀的按说话人分组；无前缀文本归属默认说话人
    （单角色镜头传 default_spk 时），否则归 None（旁白）。
    台词保留句末标点以改善 TTS 停顿。
    """
    # dialogue 兼容字符串（旧）与结构化数组（新，每项 speaker+text）
    from .minimax_prompt import norm_dialogue
    items = norm_dialogue(shot)
    if not items:
        return []
    out = []
    for it in items:
        spk = (it.get("speaker") or "").strip() or default_spk
        text = (it.get("text") or "").strip()
        if not text:
            continue
        out.append((spk or None, text))
    # 合并相邻相同说话人的片段
    merged = []
    for spk, text in out:
        if merged and merged[-1][0] == spk:
            merged[-1] = (spk, merged[-1][1] + text)
        else:
            merged.append((spk, text))
    return merged


def _char_index(script, name):
    """找角色在 characters 中的下标（用于音色稳定性）。"""
    chars = script.get("characters") or []
    for i, c in enumerate(chars):
        if str(c.get("name") or "") == name:
            return i, c
    return None, None


def _plan_timeline(segs, duration):
    """把对白句按顺序 + 字数比例排布到镜头时间轴。
    返回 [(说话人, 台词, 开始秒, 结束秒), ...]。
    """
    if not segs:
        return []
    total_chars = sum(max(1, len(t)) for _, t in segs)
    # 预留句间间隙（总长的 8%）
    gap = duration * 0.08 / max(1, len(segs))
    plan = []
    t = 0.4  # 首句从 0.4s 起，避免吞音
    for spk, text in segs:
        if not text:
            continue
        ratio = max(1, len(text)) / total_chars
        seg_dur = max(0.8, duration * ratio * 0.92)
        # 单句不超镜头剩余时间
        seg_dur = min(seg_dur, max(0.8, duration - t - 0.2))
        plan.append((spk, text, round(t, 2), round(min(duration, t + seg_dur), 2)))
        t += seg_dur + gap
        if t >= duration - 0.2:
            break
    return plan


# ---------------------------------------------------------------
# edge-tts 合成
# ---------------------------------------------------------------
def _synthesize_one(text, voice, rate="+0%", pitch="+0Hz", out_path=None):
    """用 edge-tts 合成一句对白为 mp3。返回 mp3 路径。"""
    if not out_path:
        import tempfile
        fd, out_path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
    try:
        asyncio.run(_run_edge(text, voice, rate, pitch, out_path))
    except Exception as e:
        if os.path.isfile(out_path):
            try:
                os.remove(out_path)
            except OSError:
                pass
        raise RuntimeError(f"edge-tts 合成失败：{e}")
    return out_path


async def _run_edge(text, voice, rate, pitch, out_path):
    import edge_tts
    com = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await com.save(out_path)


def _synthesize_batch(items, workdir, log=print):
    """批量合成 [(说话人, 台词, voice), ...] -> {idx: mp3路径}。
    items: list[dict(spk, text, voice)]；voice 为空则跳过。
    """
    results = {}
    os.makedirs(workdir, exist_ok=True)
    for i, it in enumerate(items):
        spk, text, voice = it.get("spk"), it.get("text"), it.get("voice")
        if not text or not voice:
            continue
        safe = re.sub(r"[^\w\u4e00-\u9fff]", "_", f"{spk}_{i}_{text[:10]}")[:60] or f"line_{i}"
        mp3 = os.path.join(workdir, f"{safe}.mp3")
        if os.path.isfile(mp3) and os.path.getsize(mp3) > 500:
            results[i] = mp3
            continue
        try:
            _synthesize_one(text, voice, out_path=mp3)
            results[i] = mp3
        except Exception as e:
            log(f"  [!] 台词{i} {spk} 合成失败：{e}")
    return results


# ---------------------------------------------------------------
# ffmpeg 混音：TTS 人声叠加到镜头视频
# ---------------------------------------------------------------
def _ffmpeg_path(ffmpeg=None):
    if ffmpeg:
        return ffmpeg
    try:
        from factory.concat import find_ffmpeg
        return find_ffmpeg()
    except Exception:
        return None


def _mix_shot_video(shot_mp4, out_mp4, timeline, voice_map, workdir, ffmpeg=None, log=print):
    """把本镜头对白 TTS 混入视频：保留原音轨（环境音），TTS 人声叠加。
    返回 True 成功 / False 失败（无对白或失败则原样复制）。
    """
    if not shot_mp4 or not os.path.isfile(shot_mp4):
        return False
    if not timeline:
        return False
    ff = _ffmpeg_path(ffmpeg)
    if not ff:
        log("  [!] 未找到 ffmpeg，TTS 混音跳过")
        return False
    # 合成本镜头所有对白
    items = []
    for spk, text, t0, t1 in timeline:
        voice = voice_map.get(spk) if isinstance(voice_map, dict) else None
        if voice:
            items.append(dict(spk=spk, text=text, voice=voice))
    if not items:
        return False
    mp3s = _synthesize_batch(items, workdir, log=log)
    if not mp3s:
        log("  [!] 无对白合成成功，保留原音轨")
        return False
    # 构建 ffmpeg 命令：每个 mp3 用 adelay 对齐到 (t0*1000)ms
    cmd = [ff, "-y", "-hide_banner", "-loglevel", "error",
           "-i", shot_mp4]
    delays = []
    for idx, (spk, text, t0, t1) in enumerate(timeline):
        mp3 = mp3s.get(idx)
        if not mp3:
            continue
        cmd += ["-i", mp3]
        delays.append(t0)
    if len(cmd) <= 4:
        return False
    # 视频 + 原音轨 + N 路 TTS，amix 全部音频（原音轨音量压低到环境底噪级）
    # 输入索引：0=视频（含原音轨 0:a），1..N=各 TTS mp3
    n_inputs = len(delays)
    filter_parts = []
    # 原音轨：压低到 20% 作为环境底噪（TTS 人声主导）
    filter_parts.append("[0:a]volume=0.2[bg]")
    tts_parts = []
    for j, d_ms in enumerate(delays):
        ai = j + 1
        filter_parts.append(f"[{ai}:a]adelay={int(d_ms*1000)}|{int(d_ms*1000)}[t{j}]")
        tts_parts.append(f"[t{j}]")
    # amix 混音：输入 = bg + 全部 TTS；TTS 音量 1.0，bg 0.2（环境底噪级）
    mix_in = "[bg]" + "".join(tts_parts)
    filter_parts.append(f"{mix_in}amix=inputs={len(delays)+1}:normalize=0[aout]")
    vf = ";".join(filter_parts)
    cmd += ["-filter_complex", vf,
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-pix_fmt", "yuv420p", out_mp4]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        log(f"  [!] TTS 混音失败：{r.stderr[-300:]}")
        return False
    return True


# ---------------------------------------------------------------
# 对外主入口：整个剧本 TTS 混音
# ---------------------------------------------------------------
def synthesize_script(script, shots_dir, output_dir=None, voice_map=None,
                      ffmpeg=None, log=print, max_workers=2):
    """遍历剧本全部镜头，为每个镜头混入 TTS 对白。
    返回 (成功镜头数, 失败镜头数, 角色音色表)。
    """
    shots = script.get("shots") or []
    if not shots:
        return 0, 0, {}
    # 构建角色音色表（整剧固定）
    role_voices = {}
    chars = script.get("characters") or []
    for i, shot in enumerate(shots, start=1):
        names = shot.get("character_refs") or shot.get("characters") or []
        for nm in names:
            if nm in role_voices:
                continue
            _, role = _char_index(script, nm)
            role_voices[nm] = _pick_voice(nm, role, voice_map=voice_map)
    # 没有角色表的：从对白说话人推断（含单角色镜头的默认说话人）
    for shot in shots:
        names = shot.get("character_refs") or shot.get("characters") or []
        dspk = names[0] if len(names) == 1 else None
        for spk, _ in _split_shot_dialogue(shot, default_spk=dspk):
            if spk and spk not in role_voices:
                _, role = _char_index(script, spk)
                role_voices[spk] = _pick_voice(spk, role, voice_map=voice_map)

    if not any(role_voices.values()):
        log("[TTS] 未匹配到任何角色音色，跳过 TTS")
        return 0, 0, role_voices

    ok = fail = 0
    for i, shot in enumerate(shots, start=1):
        src = os.path.join(shots_dir, f"shot_{i:03d}.mp4")
        if not os.path.isfile(src):
            continue
        duration = float(str(shot.get("duration_sec") or shot.get("duration") or 5).strip() or 5)
        # 单角色镜头默认说话人 = 该镜头唯一出场角色
        names = shot.get("character_refs") or shot.get("characters") or []
        default_spk = names[0] if len(names) == 1 else None
        segs = _split_shot_dialogue(shot, default_spk=default_spk)
        if not segs:
            continue
        timeline = _plan_timeline(segs, duration)
        if not timeline:
            continue
        # 每个镜头独立工作目录
        shot_work = os.path.join(output_dir or shots_dir, "tts_work", f"shot_{i:03d}")
        # 输出：直接覆盖（先合成到临时再替换）
        tmp = src + ".tts.mp4"
        if _mix_shot_video(src, tmp, timeline, role_voices, shot_work, ffmpeg=ffmpeg, log=log):
            os.replace(tmp, src)
            ok += 1
            log(f"  [TTS] 镜头{i} 配音完成（{len(timeline)} 句）")
        else:
            if os.path.isfile(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
            fail += 1
    # 输出角色音色表供日志/预览
    for nm, v in role_voices.items():
        if v:
            log(f"  [TTS] 角色音色 {nm} -> {v}")
    return ok, fail, role_voices


# 简易 CLI 自测：python -m factory.tts 文本 音色 [输出.mp3]
if __name__ == "__main__":
    text = sys.argv[1] if len(sys.argv) > 1 else "你好，欢迎使用短剧工厂。"
    voice = sys.argv[2] if len(sys.argv) > 2 else "zh-CN-XiaoxiaoNeural"
    out = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.getcwd(), "tts_test.mp3")
    _synthesize_one(text, voice, out_path=out)
    print("saved:", out)
