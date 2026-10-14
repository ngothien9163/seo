# -*- coding: utf-8 -*-
"""ollama_client — F8: một client duy nhất nói chuyện với Ollama localhost.

Mọi hàm đọc cfg LÚC GỌI (đổi settings giữa 2 lần gọi có tác dụng) và nhận seam
`post`/`get` tiêm vào → test chạy offline, không cần `ollama serve`.
`generate` chỉ retry khi Timeout; ConnectionError trả thông điệp rõ, không raise.
"""
import re
from urllib.parse import urlsplit

import requests

import config.settings as cfg

_GENERATE_SUFFIX = "/api/generate"


def base_from_url(url=None):
    u = (url or cfg.OLLAMA_URL).rstrip("/")
    if u.endswith(_GENERATE_SUFFIX):
        u = u[: -len(_GENERATE_SUFFIX)].rstrip("/")
    return u


def generate_url(base=None):
    return (base or base_from_url()) + _GENERATE_SUFFIX


def tags_url(base=None):
    return (base or base_from_url()) + "/api/tags"


def _host(url):
    return urlsplit(url).netloc or url


def _default_post(url, payload, timeout):
    return requests.post(url, json=payload, timeout=timeout)


def _default_get(url, timeout):
    return requests.get(url, timeout=timeout)


def _strip_fence(text):
    t = (text or "").strip()
    m = re.match(r"^```[a-zA-Z0-9_-]*[ \t]*\n(.*)\n```$", t, re.DOTALL)
    return m.group(1).strip() if m else t


def check_connection(get=None, url=None, timeout=5):
    """GET /api/tags. Trả {"ok","models","message"}; không bao giờ raise."""
    get = get or _default_get
    url = url or tags_url()
    try:
        resp = get(url, timeout)
    except requests.exceptions.ConnectionError:
        return {"ok": False, "models": [],
                "message": "Chưa chạy Ollama tại %s — khởi động bằng `ollama serve`." % _host(url)}
    except Exception as exc:
        return {"ok": False, "models": [], "message": "Không kiểm tra được Ollama: %s" % exc}
    if getattr(resp, "status_code", 0) != 200:
        return {"ok": False, "models": [],
                "message": "Ollama trả HTTP %s." % getattr(resp, "status_code", "?")}
    try:
        data = resp.json()
    except Exception:
        return {"ok": False, "models": [], "message": "Ollama trả về không phải JSON hợp lệ."}
    models = [m.get("name", "") for m in (data or {}).get("models", [])]
    return {"ok": True, "models": models, "message": "Ollama OK — %d model." % len(models)}


def generate(prompt, model=None, timeout=None, retries=None, post=None, url=None):
    """POST /api/generate (stream=False). Trả (text|None, error). Chỉ retry khi Timeout."""
    post = post or _default_post
    url = url or generate_url()
    model = model or cfg.CONTENT_MODEL
    timeout = cfg.CONTENT_GEN_TIMEOUT if timeout is None else timeout
    retries = cfg.CONTENT_GEN_RETRIES if retries is None else retries
    payload = {"model": model, "prompt": prompt, "stream": False}

    attempt = 0
    while True:
        try:
            resp = post(url, payload, timeout)
        except requests.exceptions.Timeout:
            if attempt < retries:
                attempt += 1
                continue
            return None, ("Ollama timeout sau %d lần thử — model lớn cần thời gian, "
                          "thử lại hoặc tăng CONTENT_GEN_TIMEOUT." % (attempt + 1))
        except requests.exceptions.ConnectionError:
            return None, "Chưa chạy Ollama tại %s — khởi động bằng `ollama serve`." % _host(url)
        except Exception as exc:
            return None, "Lỗi gọi Ollama: %s" % exc
        if getattr(resp, "status_code", 0) != 200:
            return None, "Ollama trả HTTP %s: %s" % (
                getattr(resp, "status_code", "?"), (resp.text or "")[:200])
        try:
            data = resp.json()
        except Exception:
            return None, "Ollama trả về không phải JSON hợp lệ."
        text = (data or {}).get("response")
        if text is None:
            return None, "Ollama không trả nội dung: %s" % (data or {}).get("error", "thiếu trường response")
        return _strip_fence(text), ""
