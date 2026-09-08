# -*- coding: utf-8 -*-
"""自定义 OpenAI 兼容提供商后端。

允许用户在配置 JSON 里添加任意 OpenAI 兼容的 HTTPS 提供商
（如 NVIDIA Build、硅基流动、DeepSeek、本地 vLLM 等），用于：
  - 剧本推理   : POST {base}/v1/chat/completions
  - 文生图     : POST {base}/v1/images/generations

配置格式（providers.json，可为多个，取默认或 --provider 指定）：
[
  {
    "name": "nvidia",
    "base_url": "https://integrate.api.nvidia.com",
    "api_key": "nvapi-...",
    "chat_model": "meta/llama-3.3-70b-instruct",
    "image_model": "black-forest-labs/flux.1-dev",
    "max_tokens": 12000,
    "timeout": 180,
    "default": true
  }
]

不配置时，剧本/图片仍走本机 ComfyUI 节点（现有路径不受影响）。
视频生成始终走本机 ComfyUI H3（OpenAI 无统一视频标准）。
"""
import base64
import json
import os
import time

try:
    from openai import OpenAI
    _HAS_OPENAI = True
except Exception:
    OpenAI = None
    _HAS_OPENAI = False
import urllib.request
import urllib.error


def load_providers(path=None):
    """加载提供商配置列表。path 省略时依次找：
    1. 环境变量 DRAMA_PROVIDERS
    2. 用户目录 .drama/providers.json
    3. 项目根 providers.json
    返回 list[dict]（可能为空）。
    """
    if not path:
        path = os.environ.get("DRAMA_PROVIDERS") or ""
    if not path:
        for cand in (
            os.path.join(os.path.expanduser("~"), ".drama", "providers.json"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "providers.json"),
        ):
            if os.path.isfile(cand):
                path = cand
                break
    if not path or not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def pick_provider(providers=None, name=None, path=None):
    """按 name 或 default 标记挑选一个提供商配置；无则返回 None。"""
    if providers is None:
        providers = load_providers(path=path)
    if not providers:
        return None
    if name:
        for p in providers:
            if p.get("name") == name:
                return p
        return None
    for p in providers:
        if p.get("default"):
            return p
    return providers[0]


class ProviderClient:
    """OpenAI 兼容 REST 客户端：chat（剧本推理）+ image（文生图）。"""

    def __init__(self, config, log=print):
        self.config = config
        self.base = (config.get("base_url") or "").rstrip("/")
        self.key = config.get("api_key") or ""
        self.chat_model = config.get("chat_model") or ""
        self.image_model = config.get("image_model") or ""
        self.max_tokens = int(config.get("max_tokens") or 4096)
        self.timeout = int(config.get("timeout") or 180)
        self.log = log

    # ---------- 重试策略 ----------
    @staticmethod
    def _retry_after(e):
        """从错误响应头读取 retry-after（秒）；读不到返回 None。"""
        resp = getattr(e, "response", None)
        if resp is not None:
            try:
                h = resp.headers.get("retry-after")
            except Exception:
                h = None
            if h:
                try:
                    return max(1.0, float(h))
                except (TypeError, ValueError):
                    return None
        return None

    def _is_retryable(self, e):
        """是否值得重试：429 限流 / 连接断开 / 超时 / 5xx 服务端错误。"""
        code = getattr(e, "status_code", None)
        if code is not None:
            return code == 429 or 500 <= code < 600
        name = type(e).__name__.lower()
        text = str(e).lower()
        if "429" in text or "rate_limit" in text:
            return True
        return any(t in name for t in (
            "apiconnectionerror", "apitimeouterror", "remoteprotocolerror",
            "connecterror", "readtimeout", "connecttimeout",
            "internalservererror", "badgateway", "serviceunavailable"))

    # ---------- 底层 ----------
    @staticmethod
    def _opener():
        """返回绕过系统代理的 urllib opener（本机本地代理会卡死长请求）。"""
        return urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _chat_base(self):
        """OpenAI SDK 用的 base_url：兼容"已含 /v1"与"不含 /v1"两种配置格式。

        如 https://host/radeon/v1 直接使用；https://host 则追加 /v1。
        """
        b = (self.base or "").rstrip("/")
        if b.endswith("/v1"):
            return b
        return b + "/v1"

    def _models_url(self):
        """探测 /v1/models 的完整 URL：同样兼容两种 base_url 格式。"""
        return self._chat_base() + "/models"

    def _post(self, path, payload):
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["Authorization"] = "Bearer " + self.key
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self._chat_base() + path, data=data, headers=headers, method="POST")
        try:
            with self._opener().open(req, timeout=self.timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:500]
            raise RuntimeError(f"提供商 API 错误 {e.code}（{self.base}{path}）：{body}")

    # ---------- 剧本推理 ----------
    def _vision_enabled(self):
        """图片识别（多模态输入）默认开启；配置里显式 "vision": false 可关闭。"""
        return bool(self.config.get("vision", True))

    def _build_user_content(self, user_prompt, images=None):
        """构造 user 消息 content：
        无图片时返回纯文本（保持向后兼容）；有图片且开启图片识别时返回多模态数组
        （本地图片转 data URL，http(s) 图片直接引用 URL）。
        """
        imgs = images or []
        if not imgs or not self._vision_enabled():
            return user_prompt
        content = [{"type": "text", "text": user_prompt}]
        for img in imgs:
            s = str(img)
            if s.startswith(("http://", "https://")):
                content.append({"type": "image_url", "image_url": {"url": s}})
            else:
                try:
                    with open(s, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode("ascii")
                except Exception:
                    continue
                content.append({"type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{b64}"}})
        return content

    def chat(self, system_prompt, user_prompt, temperature=0.7, max_tokens=None, images=None):
        """返回完整回复文本（content；若提供方返回 reasoning，仅返回最终答案）。

        images: 可选，list[str] 本地图片路径或 http(s) 图片 URL。
        默认开启图片识别（vision）；provider 配置 "vision": false 时忽略图片。
        """
        if not self.chat_model:
            raise RuntimeError("提供商配置缺少 chat_model")
        if not _HAS_OPENAI:
            raise RuntimeError("未安装 openai SDK，无法使用自定义提供商（pip install openai）")
        # 绕过系统代理（本机常有本地代理 127.0.0.1:xxxx，会让长请求超时/断连），直连提供商
        try:
            import httpx
            http_client = httpx.Client(trust_env=False, timeout=self.timeout)
        except Exception:
            http_client = None
        # 重试由下方手动循环统一控制（SDK 自身不重试，避免双重重试放大限流压力）
        client = OpenAI(base_url=self._chat_base(), api_key=self.key or "none",
                        http_client=http_client, timeout=self.timeout, max_retries=0)
        kwargs = {
            "model": self.chat_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": self._build_user_content(user_prompt, images)},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens or self.max_tokens,
            "stream": False,
        }
        # NVIDIA Build 的 DeepSeek/Qwen 系支持思考参数（thinking / reasoning_effort）。
        # 仅当配置显式声明 thinking 且 base_url 是 NVIDIA 时发送，
        # 其他提供商（AMD/OpenRouter 等）不支持 chat_template_kwargs，会 400 拒绝。
        if self.config.get("thinking") is not None and "nvidia" in (self.base or "").lower():
            kwargs["extra_body"] = {"chat_template_kwargs": {
                "thinking": bool(self.config["thinking"]),
                "reasoning_effort": self.config.get("reasoning_effort", "medium"),
            }}
        # AMD/DeepSeek 等提供商对连续请求有并发限流（429），长剧分幕扩写会紧接多请求；
        # 且服务器过载/限流时会直接断开连接（APIConnectionError/RemoteProtocolError）或超时。
        # 这里对可重试错误（429/连接断开/超时/5xx）做退避重试（默认最多 3 次，
        # 429 优先按服务器 retry-after 头等待），其他错误直接抛出。
        max_retries = max(0, int(self.config.get("max_retries") or 3))
        retry_base = max(1.0, float(self.config.get("retry_delay") or 3.0))
        last_err = None
        for attempt in range(max_retries + 1):
            try:
                resp = client.chat.completions.create(**kwargs)
                break
            except Exception as e:
                last_err = e
                if attempt >= max_retries or not self._is_retryable(e):
                    raise
                wait = self._retry_after(e) or min(retry_base * (2 ** attempt), 60)
                self.log(f"[提供商] 请求失败（{type(e).__name__}），"
                         f"{wait:.0f}s 后重试（{attempt + 1}/{max_retries}）…")
                time.sleep(wait)
        else:
            raise RuntimeError(
                f"提供商 API 持续失败，已重试 {max_retries} 次仍不成功：{last_err}")
        try:
            msg = resp.choices[0].message
        except (IndexError, TypeError):
            raise RuntimeError(f"chat/completions 响应结构异常：{str(resp)[:200]}")
        content = getattr(msg, "content", None)
        if not content:
            content = getattr(msg, "reasoning_content", None) or ""
        if not content:
            raise RuntimeError(f"chat/completions 未返回内容：{str(resp)[:200]}")
        return content

    # ---------- 连接测试 ----------
    def _models_list(self):
        """探测 /v1/models 并返回模型 id 列表；失败返回 []。"""
        try:
            req = urllib.request.Request(
                self._models_url(),
                headers={"Authorization": "Bearer " + self.key} if self.key else {},
                method="GET")
            with self._opener().open(req, timeout=10) as r:
                data = json.loads(r.read().decode("utf-8", "replace"))
            ids = [m.get("id") for m in (data.get("data") or []) if m.get("id")]
            return [str(x) for x in ids]
        except Exception:
            return []

    def test_connection(self, timeout=180):
        """发一个最小 chat 请求验证连通性。返回 (ok: bool, msg: str)。

        只验证能否连到提供商并完成一次推理；不要求返回特定内容。
        注意：NVIDIA 的 deepseek-v4 系实测单次响应可达 90s+（即使短内容），
        max_tokens 给足 64、用中文短消息与成功案例一致，默认超时 180s。
        """
        if not self.base:
            return False, "API 地址为空"
        if not self.chat_model:
            return False, "推理模型为空"
        ok = False
        msg = ""
        # 先试轻量的 /models 探测（部分服务不开放，失败不致命）
        try:
            req = urllib.request.Request(
                self._models_url(), headers={"Authorization": "Bearer " + self.key}, method="GET")
            with self._opener().open(req, timeout=min(timeout, 8)) as r:
                r.read()
            msg = "API 地址连通"
        except Exception as e:
            msg = f"/v1/models 不可用（{type(e).__name__}）"
        # 核心：真实 chat 请求（只发一次，给足超时）
        if _HAS_OPENAI:
            try:
                import httpx
                http_client = httpx.Client(trust_env=False, timeout=timeout)
            except Exception:
                http_client = None
            try:
                kwargs = dict(
                    model=self.chat_model,
                    messages=[{"role": "user", "content": "回复两个字：正常"}],
                    max_tokens=64, temperature=0.2, stream=False,
                )
                # 仅 NVIDIA 支持 chat_template_kwargs 思考参数，其他提供商发送会 400
                if self.config.get("thinking") is not None and "nvidia" in (self.base or "").lower():
                    kwargs["extra_body"] = {"chat_template_kwargs": {
                        "thinking": bool(self.config["thinking"]),
                        "reasoning_effort": self.config.get("reasoning_effort", "medium"),
                    }}
                client = OpenAI(base_url=self._chat_base(), api_key=self.key or "none",
                                http_client=http_client, timeout=timeout, max_retries=0)
                resp = client.chat.completions.create(**kwargs)
                try:
                    content = resp.choices[0].message.content
                except (IndexError, TypeError):
                    content = None
                if content is not None:
                    ok = True
                    msg = f"连接成功，模型 {self.chat_model} 可正常回复"
                else:
                    msg = "已连通，但模型未返回内容（检查 chat_model 是否可用）"
            except Exception as e:
                msg = f"连接失败：{e}"
                # 模型名写错/不可用时，从 /v1/models 给出候选，帮助用户快速改正
                ids = self._models_list()
                if ids:
                    guess = self.chat_model.replace(" ", "-").strip()
                    cands = [i for i in ids if i.lower() in guess.lower()
                             or guess.lower() in i.lower()] or ids[:6]
                    msg += f"\n该服务可用模型：{'、'.join(cands)}"
        else:
            ok = False
            msg = (msg + "；未安装 openai SDK，无法测试推理" if msg else "未安装 openai SDK，无法测试推理")
        return ok, msg

    # ---------- 文生图 ----------
    def image(self, prompt, size="1024x1024", n=1, save_to=None):
        """生成图片。返回 (bytes, mime)；save_to 给定时同时写文件。
        兼容 b64_json 与 url 两种返回格式。
        """
        if not self.image_model:
            raise RuntimeError("提供商配置缺少 image_model")
        payload = {
            "model": self.image_model,
            "prompt": prompt,
            "size": size,
            "n": n,
            "response_format": "b64_json",
        }
        resp = self._post("/v1/images/generations", payload)
        data = resp.get("data") or []
        if not data:
            raise RuntimeError(f"images/generations 无数据：{str(resp)[:200]}")
        first = data[0]
        mime = "image/png"
        if first.get("b64_json"):
            raw = base64.b64decode(first["b64_json"])
        elif first.get("url"):
            raw = self._download(first["url"])
            mime = "image/jpeg"
        else:
            raise RuntimeError(f"images/generations 响应不含 b64/url：{str(first)[:200]}")
        if save_to:
            os.makedirs(os.path.dirname(os.path.abspath(save_to)), exist_ok=True)
            with open(save_to, "wb") as f:
                f.write(raw)
        return raw, mime

    def _download(self, url, timeout=60):
        req = urllib.request.Request(url, headers={"User-Agent": "drama-factory"})
        with self._opener().open(req, timeout=timeout) as r:
            return r.read()


    # ---------- 剧本审核 / 修改（AI 审查员） ----------
    def review_script(self, script_json, instruction=""):
        """用用户配置的 AI 模型审核并修改剧本。

        script_json: dict，当前剧本。
        instruction: 可选，用户追加的修改要求（自然语言）。
        返回 (result_dict, raw_text)：
          - result_dict: 解析出的新剧本 dict（含 shots），审核通过时与原文一致；修改后为新剧本
          - raw_text:   模型原始返回文本
        若模型未返回可解析 JSON，返回 (None, raw_text)。
        """
        if not self.chat_model:
            raise RuntimeError("提供商配置缺少 chat_model，无法进行 AI 审核")
        prompt = (
            "你是资深短剧编剧审稿人。请审核下面这份剧本 JSON，并直接输出【修改后的完整剧本 JSON】。\n"
            "要求：\n"
            "1. 保持 JSON 结构与原剧本一致（title/character/characters/style/shots 等字段都要保留）\n"
            "2. characters 数量保持在 2-15 个，角色不能多于 15 个\n"
            "3. 修复情节漏洞、台词生硬、逻辑不通、分镜衔接跳跃等问题；\n"
            "   明显不合理或低质量处要直接改写，不要解释\n"
            "4. 若剧本已很好，可原样输出（不要添加 review 字段，输出结构必须与输入一致）\n"
            "5. 只输出 JSON，不要任何解释、前言或后语\n"
        )
        if instruction and instruction.strip():
            prompt += f"\n【用户补充修改要求】\n{instruction.strip()}\n"
        prompt += f"\n【剧本 JSON】\n{json.dumps(script_json, ensure_ascii=False, indent=2)}\n"
        text = self.chat(prompt, "请输出修改后的完整剧本 JSON", temperature=0.4)
        from factory.drama_factory import _parse_review_result
        return _parse_review_result(text), text


def write_template(path):
    """写入一份空的 providers 配置模板。"""
    template = [
        {
            "name": "example",
            "base_url": "https://integrate.api.nvidia.com",
            "api_key": "nvapi-你的key",
            "chat_model": "meta/llama-3.3-70b-instruct",
            "image_model": "black-forest-labs/flux.1-dev",
            "max_tokens": 12000,
            "timeout": 180,
            "default": True,
        }
    ]
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(template, f, ensure_ascii=False, indent=2)
    return path
