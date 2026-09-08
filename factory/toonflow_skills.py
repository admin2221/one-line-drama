# -*- coding: utf-8 -*-  
# ToonFlow prompt-engineering asset integration module (pure stdlib).  
# Integrates ToonFlow director-narrative / art-style / storyboard / video-prompt  
# skills into the Python drama factory. All functions degrade gracefully when the  
# toonflow_skills resource directory is absent: friendly text, never raises.  
import os  
  
HERE = os.path.dirname(os.path.abspath(__file__))  
SKILLS_DIR = os.path.join(HERE, 'toonflow_skills')  
  
# Chinese name - directory key mapping (story genres)  
STORY_GENRES = {  
    '\u60ac\u7591\u63a8\u7406': 'Mystery_thriller',  
    '\u751c\u5ba0\u8a00\u60c5': 'Sweet_romance_novel',  
    '\u53e4\u98ce\u4ed9\u4fa0': 'Xianxia_fantasy',  
    '\u6050\u6016\u7075\u5f02': 'Horror_supernatural',  
    '\u5bb6\u5ead\u6e29\u60c5': 'Family_warmth',  
    '\u5386\u53f2\u53f2\u8bd7': 'Historical_epic',  
    '\u70ed\u8840\u5c11\u5e74': 'Hot_blooded_action',  
    '\u5fc3\u7406\u535a\u5f08': 'Psychological_drama',  
    '\u90fd\u5e02\u804c\u573a': 'Urban_workplace_drama',  
    '\u79d1\u5e7b\u672b\u4e16': 'Scifi_post_apocalypse',  
    '\u559c\u5267\u641e\u7b11': 'Comedy_humor',  
    '\u9752\u6625\u6210\u957f': 'Coming_of_age',  
}  
  
# Chinese name - directory key mapping (art styles)  
ART_STYLES = {  
    '\u771f\u4eba\u90fd\u5e02\u5f71\u50cf\u98ce\u683c': 'realpeople_modern_city',  
    '\u0039\u0030\u5e74\u4ee3\u65e5\u5f0f\u52a8\u753b\u98ce\u683c\u8bf4\u660e': '2D_90s_japanese_anime',  
    '\u56fd\u98ce\u4e8c\u6b21\u5143\u65b0\u56fd\u6f6e\u98ce\u683c\u8bf4\u660e': '2D_chinese_guofeng',  
    '\u0033\u0044\u0020\u52a8\u753b\u6e32\u67d3\u98ce\u683c\u8bf4\u660e': '3D_anime_render',  
    '\u771f\u4eba\u53e4\u98ce\u5199\u5b9e\u98ce\u683c\u8bf4\u660e': 'realpeople_ancient_chinese',  
} 
  
def _read(path):  
    try:  
        with open(path, 'r', encoding='utf-8', errors='replace') as f:  
            return f.read()  
    except Exception:  
        return ''  
  
def _exists(path):  
    try:  
        return os.path.isfile(path)  
    except Exception:  
        return False  
  
def _norm_key(key, mapping):  
    if not key:  
        return None  
    key = str(key).strip()  
    if key in mapping:  
        return mapping[key]  
    return key  
  
def _genres_dir():  
    return os.path.join(SKILLS_DIR, 'story_skills')  
  
def _styles_dir():  
    return os.path.join(SKILLS_DIR, 'art_skills')  
  
def _list_dir_ok(d, probe):  
    try:  
        out = []  
        for sub in sorted(os.listdir(d)):  
            if _exists(os.path.join(d, sub, probe)):  
                out.append(sub)  
        return out  
    except Exception:  
        return [] 
  
def list_skills():  
    genres = _list_dir_ok(_genres_dir(), 'director_planning_narrative.md')  
    styles = _list_dir_ok(_styles_dir(), 'prefix.md')  
    files = []  
    try:  
        for r, ds, fs in os.walk(SKILLS_DIR):  
            for f in fs:  
                if f.endswith('.md'):  
                    files.append(os.path.relpath(os.path.join(r, f), SKILLS_DIR))  
    except Exception:  
        pass  
    return {'genres': genres, 'styles': styles, 'files': sorted(set(files))}  
  
def load_skill(name):  
    if not name:  
        return 'No skill file specified. Use list_skills() to see available skills.'  
    name = str(name).strip()  
    p = os.path.join(SKILLS_DIR, name)  
    if _exists(p):  
        return _read(p)  
    target = os.path.basename(name)  
    try:  
        for r, ds, fs in os.walk(SKILLS_DIR):  
            for f in fs:  
                if f == target:  
                    return _read(os.path.join(r, f))  
    except Exception:  
        pass  
    return 'Skill file not found: ' + name + ' (toonflow_skills resources may not be bundled).'  
  
def story_genre_director_prompt(genre):  
    key = _norm_key(genre, STORY_GENRES)  
    if not key:  
        return 'No story genre specified. Available: ' + ', '.join(sorted(STORY_GENRES.keys())) + '.'  
    p = os.path.join(_genres_dir(), key, 'director_planning_narrative.md')  
    if _exists(p):  
        return _read(p)  
    return 'Story genre director prompt missing for: ' + key + ' (toonflow_skills resources may not be bundled).'  
  
def art_style_prompts(style):  
    key = _norm_key(style, ART_STYLES)  
    if not key:  
        return 'No art style specified. Available: ' + ', '.join(sorted(ART_STYLES.keys())) + '.'  
    # 资源扁平存放（art_skills/<style>/art_character.md 等），无 art_prompt 子目录
    base = os.path.join(_styles_dir(), key)  
    parts = []  
    for md in ('art_character.md', 'art_scene.md', 'art_prop.md'):  
        p = os.path.join(base, md)  
        if _exists(p):  
            parts.append('===== ' + md + ' =====' + chr(10) + _read(p))  
    if not parts:  
        return 'Art style prompts missing for: ' + key + ' (toonflow_skills resources may not be bundled).'  
    return chr(10).join(parts)  
  
def available_genres():  
    return sorted(STORY_GENRES.keys()) + sorted(STORY_GENRES.values())  
  
def available_styles():  
    return sorted(ART_STYLES.keys()) + sorted(ART_STYLES.values())  
  
if __name__ == '__main__':  
    import json  
    print(json.dumps(list_skills(), ensure_ascii=False, indent=2))  
