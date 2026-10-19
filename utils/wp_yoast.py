# -*- coding: utf-8 -*-
"""utils/wp_yoast.py — F10l: Yoast focus-keyword + meta write-back sau --wp-push.

Vấn đề: `--wp-push` đẩy draft lên bằng REST /wp/v2 — WP không biết từ khóa
chính (focus keyphrase) là gì, các ô của SEO plugin trống. Lệnh này đi SAU
khi push: dò Yoast trên post, thấy thì PATCH `_yoast_wpseo_focuskw` /
`_yoast_wpseo_title` / `_yoast_wpseo_metadesc`; không Yoast thì fallback ghi
EXCERPT (core WP) + in nhắc owner tự điền Yoast.

Nguyên tắc giữ nguyên như --wp-push:
- CHỈ draft/pending — bài đã publish là quyết định của owner, PATCH bài đó bị từ chối.
- CHỈ đề xuất: meta_description lấy từ excerpt/dàn ý, owner vẫn sửa được trên WP.
- Không log credential nào (WP App Password không đi qua print).
"""
import os

import requests

from utils.wp_publisher import _basic, _urls

SEND_TIMEOUT = 30

def _settings():
    import config.settings as settings
    return settings

def _auth() -> tuple:
    """(auth header, message lỗi). Token ưu tiên env môi trường — nguồn của sự thật đã có."""
    user = str(getattr(_settings(), "WP_USER", "") or "").strip()
    password = (os.getenv("WP_APP_PASSWORD")
                or str(getattr(_settings(), "WP_APP_PASSWORD", "") or "")).strip()
    if not user or not password:
        return "", "Chưa cấu hình WP_USER + WP_APP_PASSWORD (App Password tạo trong WP admin profile)."
    return _basic(user, password), ""

def _meta_fields(focus: str, title: str, desc: str) -> dict:
    """{field Yoast: giá trị} — chỉ field CÓ giá trị; title có keyword rồi thì bỏ."""
    fields = {}
    if focus:
        fields["_yoast_wpseo_focuskw"] = focus
        if title and _fold_word(focus) not in _fold_word(title):
            fields["_yoast_wpseo_title"] = f"{title} — {focus}"[:60]
    if desc:
        fields["_yoast_wpseo_metadesc"] = desc[:156]
    return fields

def _fold_word(s: str) -> str:
    """fold không dấu để so keyword có mặt trong title (không phân biệt hoa/thường)."""
    import unicodedata
    s = (s or "").replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return " ".join(s.lower().split())

def probe_yoast(base_url: str, auth: str, post_id) -> bool:
    """GET post?context=edit → True nếu Yoast đăng ký meta fields REST."""
    endpoint, _ = _urls(base_url)
    try:
        resp = requests.get(f"{endpoint}/{post_id}",
                            headers={"Authorization": auth},
                            params={"context": "edit"},
                            timeout=SEND_TIMEOUT)
    except Exception:
        return False
    if resp.status_code != 200:
        return False
    data = resp.json() or {}
    meta = data.get("meta") or {}
    return any(k.startswith("_yoast_wpseo") for k in meta.keys()) or \
           bool(data.get("yoast_head_json"))

def patch_meta(post_id: int, focus: str = "", title: str = "",
               desc: str = "", dry_run: bool = False) -> dict:
    """{ok, mode, fields, message} — mode: 'yoast' | 'excerpt' | 'skip'."""
    try:
        base_url = str(getattr(_settings(), "WP_URL", "") or "")
        auth, err = _auth()
        if not auth:
            return {"ok": False, "mode": "skip", "fields": {}, "message": err}
        if not focus and not desc:
            return {"ok": False, "mode": "skip", "fields": {},
                    "message": "Thiếu focus keyword hoặc meta description — không PATCH gì."}
        endpoint, _ = _urls(base_url)

        # trạng thái bài: CHỈ draft/pending được đụng
        check = requests.get(f"{endpoint}/{post_id}", headers={"Authorization": auth},
                             timeout=SEND_TIMEOUT)
        if check.status_code != 200:
            return {"ok": False, "mode": "skip", "fields": {},
                    "message": f"Không đọc được post {post_id}: HTTP {check.status_code}"}
        post = check.json() or {}
        if str(post.get("status")) not in ("draft", "pending"):
            return {"ok": False, "mode": "skip", "fields": {},
                    "message": (f"Post {post_id} đã publish là quyết định của owner — "
                                "không PATCH meta sau publish.")}

        fields = _meta_fields(focus or "", title or str(post.get("title", {}).get("raw", "")),
                              desc or str(post.get("excerpt", {}).get("raw") or ""))
        if dry_run:
            return {"ok": True, "mode": "dry-run", "fields": fields,
                    "message": "(dry-run) sẽ PATCH các field trên."}

        if probe_yoast(base_url, auth, post_id):
            payload = {"meta": fields}
            mode = "yoast"
        else:
            # Yoast không expose REST → chỉ PATCH excerpt (core WP an toàn)
            payload = {"excerpt": (desc or str(post.get("excerpt", {}).get("raw") or ""))[:156]}
            mode = "excerpt"
        resp = requests.put(f"{endpoint}/{post_id}",
                            headers={"Authorization": auth, "Content-Type": "application/json"},
                            json=payload, timeout=SEND_TIMEOUT)
        if resp.status_code in (200, 201):
            note = (f"Đã PATCH Yoast meta (id {post_id})." if mode == "yoast"
                    else f"Không dò thấy Yoast qua REST — chỉ PATCH excerpt (id {post_id}); "
                         "nhắc owner tự điền Yoast focus keyword.")
            return {"ok": True, "mode": mode, "fields": fields, "message": note}
        return {"ok": False, "mode": mode, "fields": fields,
                "message": f"WordPress từ chối PATCH: HTTP {resp.status_code} {resp.text[:160]}"}
    except requests.exceptions.ConnectionError as e:
        return {"ok": False, "mode": "skip", "fields": {},
                "message": f"Không kết nối được WordPress: {e}"}
    except Exception as e:
        return {"ok": False, "mode": "skip", "fields": {},
                "message": f"Lỗi gọi WordPress: {type(e).__name__}: {e}"}

def run_yoast_cli(post_id: str = "", keyword: str = "") -> int:
    """Entry CLI: --yoast-meta <post_id> [--kw "từ khóa"] — patch/fallback sau push."""
    import config.settings as settings

    pid = str(post_id or "").strip()
    kw = str(keyword or "").strip()
    if not pid or not pid.isdigit():
        print('  Dùng: python main.py --yoast-meta <post_id> --kw "từ khóa"')
        print("  (post_id lấy từ dòng kết quả --wp-push; --kw là focus keyphrase)")
        return 2
    result = patch_meta(int(pid), focus=kw,
                        desc=kw and f"Tất cả về {kw} — bài viết hướng dẫn tại "
                                    f"{getattr(settings, 'TARGET_URL', '') or 'site'}")
    print("[Yoast] " + result["message"])
    for k, v in (result.get("fields") or {}).items():
        shown = v if isinstance(v, str) and len(v) < 70 else (str(v)[:67] + "...")
        print(f"  {k} = {shown}")
    return 0 if result.get("ok") else 1
