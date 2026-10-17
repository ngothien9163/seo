"""
utils/keywords.py — Một điểm đọc/duyệt duy nhất cho danh sách từ khóa (F2).

Từ khóa sống ở `config/keywords.json` (schema {"site", "keywords"}), không phải
biến list trong settings.py — để F10 (multi-site) chỉ việc đổi path của KEYWORDS_FILE.

    load_keywords() -> list[str]              # đọc, file thiếu/sai -> []
    save_keywords(list, site=None)            # chuẩn hóa + ghi atomic
    add_keyword("nối mi quận 7") -> (bool, str)  # chống trùng theo fold dấu
    site_domain() -> str                      # domain của cfg.TARGET_URL

Trùng/không trùng so theo _fold của gsc_client: "noi mi quan 2" == "nối mi quận 2".

Ghi chú: chỉ stdlib ở đầu file — module này được import từ CLI/GUI/rank tracker,
không được kéo theo playwright hay requests (import lười trong hàm).
"""
import json
import os

import utils.site_paths as _site_paths

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_KW_NAME = "keywords.json"
_DEFAULT_KEYWORDS_FILE = _site_paths.site_config(_KW_NAME)
# Slot override cho test/CLI (test gán KEYWORDS_FILE); code đọc qua _keywords_path().
KEYWORDS_FILE = _DEFAULT_KEYWORDS_FILE


def _keywords_path() -> str:
    """Đường dẫn keywords.json lúc gọi. Test gán KEYWORDS_FILE → tôn trọng; không → resolve per-site."""
    if KEYWORDS_FILE != _DEFAULT_KEYWORDS_FILE:
        return KEYWORDS_FILE
    return _site_paths.site_config(_KW_NAME)


def _fold(s: str) -> str:
    """Fold không dấu ('Nối Mi Thủ Đức' → 'noi mi thu duc') — tái dùng bản của gsc_client.

    Import trong hàm: `gsc_client` kéo theo `requests`, module này phải load được
    cả ở những nơi chưa cần tới Search Console API.
    """
    from utils.gsc_client import _fold as gsc_fold
    return gsc_fold(s)


def site_domain() -> str:
    """Domain mục tiêu từ cfg.TARGET_URL — 'https://WWW.Site.com/x' → 'site.com'.

    Ủy quyền cho site_paths._domain thay vì giữ bản copy thứ hai: hai bản đã lệch nhau
    (bản cũ bỏ sót input dạng path trần — 'shoplanhdep.com/blog' trả nguyên cả path) và
    domain này còn được ghi vào keywords.json nên lệch là lệch dữ liệu.
    """
    return _site_paths.site_domain()


def load_keywords() -> list[str]:
    """Danh sách từ khóa đang theo dõi. File thiếu/hỏng → [] (không raise)."""
    if not os.path.exists(_keywords_path()):
        return []
    try:
        with open(_keywords_path(), encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    if isinstance(data, list):  # tay người sửa file thành list trần vẫn đọc được
        raw = data
    elif isinstance(data, dict):
        raw = data.get("keywords") or []
    else:
        return []
    return [str(k) for k in raw if isinstance(k, str) and k.strip()]


def _normalize(keywords) -> list[str]:
    """Bỏ phần tử rác, trim, gỡ trùng theo fold (giữ lần xuất hiện đầu, giữ nguyên dấu)."""
    if keywords is None:
        return []
    out, seen = [], set()
    for k in keywords:
        if not isinstance(k, str):
            continue
        k = " ".join(k.strip().split())
        if not k:
            continue
        key = _fold(k)
        if key in seen:
            continue
        seen.add(key)
        out.append(k)
    return out


def save_keywords(keywords, site: str = None) -> None:
    """Ghi danh sách từ khóa (chuẩn hóa) vào keywords.json — atomic qua file tạm."""
    payload = {"site": site or site_domain(), "keywords": _normalize(keywords)}
    path = _keywords_path()
    tmp = path + ".tmp"
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def add_keyword(kw) -> tuple[bool, str]:
    """Thêm một từ khóa vào danh sách. Trả (đã thêm chưa, thông điệp tiếng Việt)."""
    if not isinstance(kw, str):
        return False, "Từ khóa phải là một chuỗi — không có gì được thêm."
    kw = " ".join(kw.strip().split())
    if not kw:
        return False, "Từ khóa rỗng — không có gì được thêm."

    current = load_keywords()
    for existing in current:
        if _fold(existing) == _fold(kw):
            return False, f"'{kw}' đã có trong danh sách (đang là '{existing}')."

    save_keywords(current + [kw])
    return True, f"Đã thêm '{kw}' — tổng {len(current) + 1} từ khóa đang theo dõi."
