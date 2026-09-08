# -*- coding: utf-8 -*-
"""ComfyUI HTTP API 客户端：提交 prompt、轮询、读历史、上传/下载文件。"""
import json
import os
import time
import uuid
import urllib.request
import urllib.error

try:
    import requests
    _HAS_REQUESTS = True
except Exception:
    _HAS_REQUESTS = False


class ComfyClient:
    def __init__(self, base_url="http://127.0.0.1:8188", timeout=10, poll_interval=2.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.poll_interval = poll_interval

    # ---------- low level ----------
    def _get_json(self, path):
        with urllib.request.urlopen(f"{self.base_url}{path}", timeout=self.timeout) as r:
            return json.loads(r.read().decode())

    def _post_json(self, path, payload):
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}{path}", data=data,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read().decode())

    def health(self):
        try:
            s = self._get_json("/system_stats")
            return s.get("system", {})
        except Exception as e:
            return {"error": str(e)}

    # ---------- queue / prompt ----------
    def queue_prompt(self, api_prompt, client_id=None):
        if client_id is None:
            client_id = uuid.uuid4().hex
        return self._post_json("/prompt", {"prompt": api_prompt, "client_id": client_id})

    def interrupt(self):
        try:
            return self._post_json("/interrupt", {})
        except Exception:
            return None

    def get_queue(self):
        return self._get_json("/queue")

    def get_history(self, prompt_id):
        return self._get_json(f"/history/{prompt_id}")

    def wait_done(self, prompt_id, on_progress=None, max_wait=None):
        """阻塞等待 prompt 完成，返回 history 条目；失败返回 {'error': ...}。"""
        start = time.time()
        while True:
            if max_wait and (time.time() - start) > max_wait:
                return {"error": "timeout", "prompt_id": prompt_id}
            try:
                h = self.get_history(prompt_id)
            except Exception as e:
                time.sleep(self.poll_interval)
                continue
            if prompt_id in h:
                entry = h[prompt_id]
                status = entry.get("status", {})
                if status.get("completed") or status.get("status_str") == "success":
                    return entry
                if status.get("status_str") == "error":
                    return {"error": "execution error", "prompt_id": prompt_id, "entry": entry}
            if on_progress:
                try:
                    on_progress()
                except Exception:
                    pass
            time.sleep(self.poll_interval)

    # ---------- outputs extraction ----------
    @staticmethod
    def extract_outputs(entry):
        """从 history 条目提取 outputs，返回 {node_id: {output_name: value}}。"""
        return entry.get("outputs", {})

    @staticmethod
    def first_image(entry):
        """返回第一个图片输出 (filename, subfolder, type)。"""
        for nid, outs in entry.get("outputs", {}).items():
            for k, v in outs.items():
                if isinstance(v, list) and v and isinstance(v[0], dict) and "filename" in v[0]:
                    f = v[0]
                    return f.get("filename"), f.get("subfolder", ""), f.get("type", "output")
        return None, None, None

    @staticmethod
    def first_text(entry):
        """提取第一个文本输出（适配 'text' / 'string' 两种 key）。"""
        for nid, outs in entry.get("outputs", {}).items():
            if isinstance(outs, dict):
                for k in ("text", "string"):
                    if k in outs:
                        v = outs[k]
                        if isinstance(v, list) and v:
                            return str(v[0])
                        if isinstance(v, str) and v:
                            return v
        return None

    # ---------- file transfer ----------
    def upload_image(self, file_path, overwrite=True, subfolder=""):
        """上传图片到 ComfyUI input 目录，返回服务器文件名。"""
        if _HAS_REQUESTS:
            with open(file_path, "rb") as f:
                _low = os.path.basename(file_path).lower()
                _mime = ("image/jpeg" if _low.endswith((".jpg", ".jpeg"))
                         else "image/webp" if _low.endswith(".webp") else "image/png")
                files = {"image": (os.path.basename(file_path), f, _mime)}
                data = {"overwrite": str(overwrite).lower(), "type": "input", "subfolder": subfolder}
                r = requests.post(f"{self.base_url}/upload/image", files=files, data=data, timeout=self.timeout * 6)
                r.raise_for_status()
                return r.json()
        # fallback: manual multipart
        boundary = "----ComfyFactoryBoundary" + uuid.uuid4().hex
        name = os.path.basename(file_path)
        parts = []
        for k, v in [("overwrite", str(overwrite).lower()), ("type", "input"), ("subfolder", subfolder)]:
            parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n")
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{name}\"\r\n"
            f"Content-Type: image/png\r\n\r\n")
        with open(file_path, "rb") as f:
            body = ("".join(parts)).encode("utf-8") + f.read() + f"\r\n--{boundary}--\r\n".encode()
        req = urllib.request.Request(
            f"{self.base_url}/upload/image", data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout * 6) as r:
            return json.loads(r.read().decode())

    def view_image(self, filename, subfolder="", type_="output", save_to=None):
        """通过 /view 下载图片；save_to 省略则返回字节。"""
        params = f"?filename={urllib.request.quote(filename)}&subfolder={urllib.request.quote(subfolder)}&type={type_}"
        with urllib.request.urlopen(f"{self.base_url}/view{params}", timeout=self.timeout * 6) as r:
            data = r.read()
        if save_to:
            os.makedirs(os.path.dirname(save_to), exist_ok=True)
            with open(save_to, "wb") as f:
                f.write(data)
            return save_to
        return data
