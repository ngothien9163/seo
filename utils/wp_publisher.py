# -*- coding: utf-8 -*-
"""
utils/wp_publisher.py — C1: đẩy một bản nháp .md từ content/drafts/ lên WordPress
với status DRAFT (hoặc pending.', không bao gì 'publish'.

Thiết kế giữ triết lý F8: tool đẩy cây lau, người dùng duyệt trên WP rồi mới
publish bằng tay. Vậy nên:
- POST /wp-json/wp/v2/posts {status: "draft", title, content, excerpt} qua
  HTTP Basic (Application Password — WP tạo trong trang cá nhân của admin,
  username + "xxxx xxxx xxxx" password riêng cho app, không là mật khẩu login).
- status mặc định "draft"; `--status pending` là trần chốt (publish/pri valet
  bị TỪ CHỐI ở validate — không đường tắt nào publish từ tool).
- frontmatter .md được bóc ra: keyword → dùng tìm title nếu --title thiếu,
  các key còn lại KHÔNG nặn thành tag/category (WP có id riêng — thêm tay).

Chạy:
    python main.py --wp-push content/drafts/<file>.md
    python main.py --wp-push <file>.md --title "..." --excerpt "..."  # override
Cấu hình WP_URL / WP_USER / WP_APP_PASSWORD trong settings PHẦN L (mới) —
password là secret (biến môi trường WP_APP_PASSWORD thắng settings, không log).
"""
import json
import os
import re
from urllib.parse import urlsplit

import requests

import config.settings as cfg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SEND_TIMEOUT = 30
ALLOWED_STATUS = ("draft", "pending")

_FRONT_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


class PublishError(Exception):
    pass


def _basic(user: str, app_password: str) -> str:
    import base64
    raw = f"{user}:{app_password}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def validate_status(status: str) -> str:
    s = (status or "draft").strip().lower()
    if s not in ALLOWED_STATUS:
        raise PublishError(
            f"Chỉ cho phép status {' / '.join(ALLOWED_STATUS)} — tool chỉ đẩy bản nháp "
            f"để owner duyệt; publish là ranh giới bạn chốt trên WP, không có đường tắt.")
    return s


def _strip_frontmatter(text: str) -> tuple[dict, str]:
    """(meta dict, thân markdown) — file không có frontmatter → ({}, text nguyên)."""
    m = _FRONT_RE.match(text or "")
    if not m:
        return {}, (text or "").strip()
    raw = m.group(1)
    body = (text or "")[m.end():].strip()
    meta = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k, v = k.strip(), v.strip().strip('"')
        if k and v:
            meta[k] = v
    return meta, body


def _extract_title(body: str, meta: dict) -> str:
    """Thứ tự title: frontmatter 'title' → H1 đầu tiên → từ khóa người dùng gone."""
    if isinstance(meta, dict):
        t = (meta.get("title") or "").strip()
        if t:
            return t
    for ln in (body or "").splitlines():
        if ln.strip().startswith("# "):
            return ln.strip()[2:].strip()
    return ""


def _urls(base_url: str) -> tuple[str, str]:
    base = (base_url or "").strip()
    if not base:
        raise PublishError("Chưa cấu hình WP_URL (VD: https://nankybeauty.com).")
    rest = base.rstrip("/") + "/wp-json/wp/v2"
    return rest + "/posts", rest


def push_draft(title: str, markdown: str, excerpt: str = "",
               status: str = "draft", slug: str = "") -> dict:
    """POST một bài DRAFT lên WP. Trả dict {ok, id, link, message}. Không raise."""
    try:
        status = validate_status(status)
        endpoint, _ = _urls(getattr(cfg, "WP_URL", "") or "")
        user = str(getattr(cfg, "WP_USER", "") or "").strip()
        password = (os.getenv("WP_APP_PASSWORD")
                    or str(getattr(cfg, "WP_APP_PASSWORD", "") or "")).strip()
        if not user or not password:
            return {"ok": False, "message": ("Chưa cấu hình WP_USER + WP_APP_PASSWORD "
                                             "(App Password tạo trong WP admin profile).")}
        if not title:
            return {"ok": False, "message": "Thiếu title — thêm --title \"...\"."}
        if not markdown:
            return {"ok": False, "message": "Thiếu nội dung bài."}
        resp = requests.post(
            endpoint,
            headers={"Authorization": _basic(user, password),
                     "Content-Type": "application/json"},
            json={"title": title, "content": markdown, "excerpt": excerpt,
                  "status": status, **({"slug": slug} if slug else {})},
            timeout=SEND_TIMEOUT)
    except PublishError as e:
        return {"ok": False, "message": str(e)}
    except requests.exceptions.ConnectionError as e:
        return {"ok": False, "message": f"Không kết nối được WordPress: {e}"}
    except Exception as e:
        return {"ok": False, "message": f"Lỗi gọi WordPress: {type(e).__name__}: {e}"}
    try:
        data = resp.json()
    except Exception:
        data = {}
    if resp.status_code in (200, 201):
        return {"ok": True, "id": data.get("id"), "link": data.get("link"),
                "message": f"Đã tải lên '{title}' với status: {data.get('status', status)} "
                           f"(id {data.get('id')}) — duyệt trên WP rồi publish bằng tay."}
    msg = (data or {}).get("message") or resp.text[:200]
    return {"ok": False, "code": data.get("code"), "message": f"WordPress từ chối: {msg}"}


def push_file(path: str, status: str = "draft", title_override: str = "",
              excerpt_override: str = "") -> dict:
    """Đọc file draft .md → bóc frontmatter → push_draft. Trả kết quả push_draft."""
    path = (path or "").strip().strip('"')
    if not path:
        return {"ok": False, "message": "Thiếu đường dẫn file .md."}
    if not os.path.isfile(path):
        return {"ok": False, "message": f"Không tìm thấy file: {path}"}
    try:
        text = open(path, encoding="utf-8").read()
    except OSError as e:
        return {"ok": False, "message": f"Không đọc được file: {e}"}
    meta, body = _strip_frontmatter(text)
    title = title_override or _extract_title(body, meta)
    if not title:
        title = meta.get("keyword", "") or os.path.splitext(os.path.basename(path))[0]
    excerpt = excerpt_override or meta.get("excerpt", "") or meta.get("topic", "") or ""
    from utils.content_prompts import slugify
    return push_draft(title=title, markdown=body, excerpt=excerpt, status=status,
                      slug=slugify(meta.get("keyword") or title))


def validate_origin_consistency() -> str:
    """Kiểm tra WP_URL có cùng domain TARGET_URL (cảnh báo nhẹ, không chặn) —
    site khác nhau thì dữ liệu xếp hạng ≠ site bài viết. Trả chuỗi cảnh báo/''."""
    base = (getattr(cfg, "WP_URL", "") or "").strip()
    if not base:
        return ""
    try:
        h = (urlsplit(base).netloc or "").lower().removeprefix("www.")
    except Exception:
        return ""
    target = (getattr(cfg, "TARGET_URL", "") or "")
    try:
        th = (urlsplit(target).netloc or "").lower().removeprefix("www.")
    except Exception:
        th = ""
    if th and h != th:
        return (f"⚠️ WP_URL ({h}) khác TARGET_URL ({th}) — báo cáo xếp hạng của "
                f"site khác với site nhận bài nháp, cân nhắc trước khi đẩy.")
    return ""


def run_push_cli(path: str, status: str = "draft", title: str = "",
                 excerpt: str = "") -> int:
    """Entry `--wp-push`: đẩy 1 file .md. Exit 0 ok / 1 lỗi WP - cấu hình / 2 thiếu input."""
    if not path:
        print('[WP] Thiếu file — python main.py --wp-push content/drafts/<file>.md '
              '[--title "..."] [--excerpt "..."] [--status draft|pending]')
        return 2
    result = push_file(path, status=status, title_override=title,
                       excerpt_override=excerpt)
    warn = validate_origin_consistency()
    prefix = "[WP] "
    if result["ok"]:
        print(prefix + "OK " + result["message"])
        if result.get("link"):
            print(prefix + f"Xem bản nháp: {result['link']}")
        return 0
    msg = str(result["message"])
    print(prefix + ("Lỗi " if ("Chưa cấu hình" not in msg and "Không tìm thấy"
                               not in msg and "Không đọc được" not in msg)
                    else "Xem lại ") + msg)
    if warn:
        print(prefix + warn)
    return 1
