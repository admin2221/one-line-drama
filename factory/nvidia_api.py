# -*- coding: utf-8 -*-
"""NVIDIA FLUX 云端文生图客户端（ai.api.nvidia.com /v1/genai 端点）。

用于把"角色定妆图/场景/物品参考图"改由云端 FLUX 生成（GUI"生图方式=API"），
替代本机 ComfyUI 的 Z-Image 文生图；生成的 PNG 仍会上传回本机 ComfyUI input
目录，供 H3 ref2va 视频工作流当参考图使用。

配置（image_api.json，GUI"生图API设置…"弹窗生成）：
{
  "endpoint": "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.2-klein-4b",
  "api_key": "nvapi-...",
  "width": 1024,
  "height": 1024,
  "steps": 4
}

仅使用标准库（urllib），不依赖 requests/openai。
"""
import base64
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request

DEFAULT_ENDPOINT = "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.2-klein-4b"
DEFAULT_WIDTH = 1024
DEFAULT_HEIGHT = 1024
DEFAULT_STEPS = 4
DEFAULT_TIMEOUT = 180
CONFIG_NAME = "image_api.json"


def _default_search_dirs():
    """配置自动发现的搜索目录：exe 同目录（frozen）→ 工程目录 → cwd。"""
    dirs = []
    if getattr(sys, "frozen", False):
        dirs.append(os.path.dirname(os.path.abspath(sys.executable)))
    dirs.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 工程/源码目录
    dirs.append(os.getcwd())
    out = []
    for d in dirs:
        if d and d not in out:
            out.append(d)
    return out


def find_image_api_config(path=None):
    """查找生图 API 配置文件路径；未找到返回 None。

    path 优先；省略时依次找 exe 同目录 / 工程目录 / cwd 下的 image_api.json。
    """
    if path:
        return path if os.path.isfile(path) else None
    for d in _default_search_dirs():
        cand = os.path.join(d, CONFIG_NAME)
        if os.path.isfile(cand):
            return cand
    return None


def load_image_api_config(path=None):
    """加载配置为 dict；失败/缺失返回 None。"""
    p = find_image_api_config(path)
    if not p:
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


class NvidiaFluxError(RuntimeError):
    pass


class NvidiaFluxClient:
    """FLUX 文生图 REST 客户端：POST {endpoint}，响应 {artifacts:[{base64,...}]}。"""

    def __init__(self, config=None, endpoint=None, api_key=None,
                 width=None, height=None, steps=None, timeout=DEFAULT_TIMEOUT, log=print):
        config = config or {}
        self.endpoint = (endpoint or config.get("endpoint") or DEFAULT_ENDPOINT).rstrip("/")
        self.api_key = api_key or config.get("api_key") or ""
        self.width = int(width or config.get("width") or DEFAULT_WIDTH)
        self.height = int(height or config.get("height") or DEFAULT_HEIGHT)
        self.steps = int(steps or config.get("steps") or DEFAULT_STEPS)
        self.timeout = int(timeout or config.get("timeout") or DEFAULT_TIMEOUT)
        self.log = log
        if not self.api_key:
            raise NvidiaFluxError("NVIDIA 生图 API 缺少 api_key，请在 GUI“生图API设置”中填写并保存")

    # ---------- 底层 ----------
    @staticmethod
    def _opener():
        """绕过系统代理（本机本地代理会卡死长请求），与 provider.py 一致。"""
        return urllib.request.build_opener(urllib.request.ProxyHandler({}))

    @staticmethod
    def _retry_after(e):
        try:
            h = e.headers.get("retry-after")
        except Exception:
            h = None
        if h:
            try:
                return max(1.0, float(h))
            except (TypeError, ValueError):
                return None
        return None

    def _is_retryable(self, e):
        code = getattr(e, "code", None)
        if code is not None:
            return code == 429 or 500 <= code < 600
        name = type(e).__name__.lower()
        text = str(e).lower()
        if "429" in text or "rate_limit" in text:
            return True
        return any(t in name for t in (
            "timeout", "connectionerror", "connectionreset",
            "remoteprotocolerror", "internalservererror", "badgateway",
            "serviceunavailable", "sslerror"))

    # ---------- 生图 ----------
    def generate_image(self, prompt, width=None, height=None, steps=None, seed=None):
        """调用 FLUX 端点生成一张图。

        返回 PNG bytes；失败抛 NvidiaFluxError。
        """
        if not prompt or not str(prompt).strip():
            raise NvidiaFluxError("NVIDIA 生图 prompt 为空")
        w = int(width or self.width)
        h = int(height or self.height)
        s = int(steps or self.steps)
        if seed is None:
            seed = random.randint(0, 2 ** 32 - 1)  # NVIDIA 端点要求 seed < 2^32
        payload = {"prompt": str(prompt).strip(),
                   "width": w, "height": h, "seed": int(seed), "steps": s}
        headers = {
            "Authorization": "Bearer " + self.api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.endpoint, data=data, headers=headers, method="POST")

        last = None
        for attempt in range(4):
            try:
                with self._opener().open(req, timeout=self.timeout) as r:
                    resp = json.loads(r.read().decode("utf-8", "replace"))
                break
            except urllib.error.HTTPError as e:
                last = e
                body = ""
                try:
                    body = e.read().decode("utf-8", "replace")[:300]
                except Exception:
                    pass
                if attempt >= 3 or not self._is_retryable(e):
                    raise NvidiaFluxError(
                        f"NVIDIA 生图 API 错误 {e.code}：{body or e.reason}") from e
                wait = self._retry_after(e) or min(2 * (2 ** attempt), 30)
                self.log(f"[NVIDIA生图] HTTP {e.code}，{wait:.0f}s 后重试（{attempt + 1}/3）")
                time.sleep(wait)
            except Exception as e:
                last = e
                if attempt >= 3 or not self._is_retryable(e):
                    raise NvidiaFluxError(f"NVIDIA 生图请求失败：{e}") from e
                wait = min(2 * (2 ** attempt), 30)
                self.log(f"[NVIDIA生图] {type(e).__name__}，{wait:.0f}s 后重试（{attempt + 1}/3）")
                time.sleep(wait)
        else:
            raise NvidiaFluxError(f"NVIDIA 生图持续失败：{last}")

        arts = resp.get("artifacts") or resp.get("images") or []
        if not arts:
            raise NvidiaFluxError(
                f"NVIDIA 生图响应无图片数据：{json.dumps(resp, ensure_ascii=False)[:300]}")
        first = arts[0]
        b64 = first.get("base64") or (first.get("image") if isinstance(first.get("image"), str) else "")
        if not b64:
            raise NvidiaFluxError(f"NVIDIA 生图响应缺少 base64：{str(first)[:200]}")
        try:
            raw = base64.b64decode(b64)
        except Exception as e:
            raise NvidiaFluxError(f"NVIDIA 生图 base64 解码失败：{e}") from e
        if not raw:
            raise NvidiaFluxError("NVIDIA 生图返回空字节")
        return raw
