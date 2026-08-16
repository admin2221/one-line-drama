"""一句话短剧全自动流水线 - 一键运行引擎
通过 ComfyUI API 加载并执行 master 工作流，实现：
一句话 -> LLM剧本(4镜头) -> Z-Image参考图 -> H3视频 -> 拼接 -> 完整短剧

用法:
  python run_drama_pipeline.py "一句话剧情" [--watch]
"""
import json
import sys
import time
import urllib.request
import urllib.parse

API = "http://127.0.0.1:8188"
WORKFLOW = r"D:\Comfyui\Comfyui\user\default\workflows\一句话短剧全自动流水线.json"
sys.path.insert(0, r"D:\Comfyui\Comfyui\scripts")
from wf2api_full import workflow_to_api


def submit(prompt, client_id="drama_pipeline"):
    data = json.dumps({"prompt": prompt, "client_id": client_id}).encode()
    req = urllib.request.Request(API + "/prompt", data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"http_error": e.read().decode()}


def wait_done(prompt_id, timeout=5400):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(f"{API}/history/{prompt_id}", timeout=10) as resp:
                h = json.loads(resp.read().decode())
            if prompt_id in h:
                st = h[prompt_id]["status"]
                if st.get("completed") or st.get("status_str") in ("success", "error"):
                    return h[prompt_id]
        except Exception:
            pass
        time.sleep(10)
    return None


def set_story(prompt, story):
    """把一句话写入 llm_director 的 custom_prompt 输入（覆盖 story 链接）。"""
    for nid, node in prompt.items():
        if node["class_type"] == "llama_cpp_instruct_adv":
            node["inputs"]["custom_prompt"] = story  # 覆盖链接为字符串
    return prompt


def main():
    story = sys.argv[1] if len(sys.argv) > 1 else "一个落魄书生在雨夜捡到一枚能穿越时空的古镜，他回到过去改变了命运，却发现镜中自己的脸越来越模糊。"
    wf = json.load(open(WORKFLOW, encoding="utf-8"))
    prompt = workflow_to_api(wf)
    prompt = set_story(prompt, story)

    print("提交一句话短剧流水线...")
    r = submit(prompt)
    if "http_error" in r:
        print("提交失败:", r["http_error"][:1500])
        sys.exit(1)
    pid = r.get("prompt_id")
    print("已排队:", pid)

    if "--watch" in sys.argv:
        print("监控执行进度（每10秒刷新）...")
        res = wait_done(pid)
        if res is None:
            print("超时")
            sys.exit(1)
        st = res["status"]
        print("状态:", st.get("status_str"))
        if st.get("messages"):
            for m in st["messages"]:
                if m[0] == "execution_error":
                    print("错误节点:", m[1].get("node_id"), m[1].get("node_type"))
                    print(m[1].get("exception_message", "")[:2000])
        outs = res.get("outputs", {})
        for nid, o in outs.items():
            if "videos" in o:
                for v in o["videos"]:
                    print("输出视频:", v.get("filename"), "->", v.get("subfolder", ""))
            if "images" in o:
                for im in o["images"]:
                    print("输出图片:", im.get("filename"))
    else:
        print("已提交。加 --watch 参数可监控进度。")


if __name__ == "__main__":
    main()
