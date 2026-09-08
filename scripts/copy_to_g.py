# -*- coding: utf-8 -*-
"""复制 comfyui-drama 本次生成相关文件到 G:\\短剧项目。

结构：
  G:\\短剧项目\\引擎    -> factory + characters + scripts + README + workflows
  G:\\短剧项目\\技能    -> drama-shorts-generator（本次创建）
  G:\\短剧项目\\成片    -> output\\*\\final_drama.mp4（逐剧成片，单独子目录）
  G:\\短剧项目\\剧本    -> output\\*\\script.json
"""
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")
SRC = r"D:\Comfyui\comfyui-drama"
DST = r"G:\短剧项目"


def _copy_tree(src, dst):
    if os.path.isdir(src):
        shutil.copytree(src, dst, dirs_exist_ok=True)
    elif os.path.isfile(src):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)


def main():
    # 1) 引擎
    eng_dst = os.path.join(DST, "引擎")
    for sub in ["factory", "characters", "scripts", "workflows"]:
        _copy_tree(os.path.join(SRC, sub), os.path.join(eng_dst, sub))
    for f in ["README.md"]:
        _copy_tree(os.path.join(SRC, f), os.path.join(eng_dst, f))
    print("引擎 OK")

    # 2) 技能
    skill_src = os.path.join(
        os.environ.get("APPDATA", ""),
        "com.chaitin.baizhi.monkeycode", "ohmyagent", "skills", "drama-shorts-generator")
    if os.path.isdir(skill_src):
        _copy_tree(skill_src, os.path.join(DST, "技能", "drama-shorts-generator"))
        print("技能 OK")
    else:
        print("技能目录未找到:", skill_src)

    # 3) 成片（output 下所有含 final_drama.mp4 的剧）
    out_root = os.path.join(SRC, "output")
    films_dst = os.path.join(DST, "成片")
    scripts_dst = os.path.join(DST, "剧本")
    n_films = 0
    if os.path.isdir(out_root):
        for d in os.listdir(out_root):
            sub = os.path.join(out_root, d)
            if not os.path.isdir(sub):
                continue
            film = os.path.join(sub, "final_drama.mp4")
            if os.path.isfile(film):
                _copy_tree(film, os.path.join(films_dst, d, "final_drama.mp4"))
                n_films += 1
            script = os.path.join(sub, "script.json")
            if os.path.isfile(script):
                _copy_tree(script, os.path.join(scripts_dst, d, "script.json"))
    print("成片 OK, 共", n_films, "部")

    print("复制完成 →", DST)


if __name__ == "__main__":
    main()
