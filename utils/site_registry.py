# -*- coding: utf-8 -*-
"""utils/site_registry.py — F10b: sổ đăng ký site (config/sites.json).

F10 cũ: "site = đâu ra đó" — slug suy từ cfg.TARGET_URL đột thời, muốn nhớ
danh sách site của mình thì phải lục thư mục data/. File này cho danh sách
site một NHÀ: `config/sites.json` (schema `{"sites": [{"url", "label",
"added"}]}`, atomic ghi qua file tạm như mọi state khác).

KHÔNG đụng cơ chế resolve đường dẫn của site_paths: một site chỉ "dữ liệu
đã tách riêng" khi data/<slug>/.migrated tồn tại (F10) — sổ lưu URL, việc
suy slug từ URL vẫn là việc của site_paths lúc gọi. Thêm site vào sổ
KHÔNG tự migrate; bảng trạng thái chỉ đối chiếu, không vỗ ngực thay F10.

Chỉ stdlib; hàm nhận tham số để test thuần (không đụng file/network khi import).
"""
import json
import os
import urllib.parse
from datetime import date

import utils.site_paths as sp

REGISTRY_NAME = "sites.json"

ERROR_NOT_URL = "không đọc được domain — không có gì được thêm"
ERROR_DUPLICATE = "site này đã có trong sổ rồi"


def _registry_path(base_dir: str = None) -> str:
    """config/sites.json — luôn ở CONFIG_ROOT (sổ dùng chung, không phải state per-site)."""
    root = base_dir if base_dir is not None else sp.CONFIG_ROOT
    return os.path.join(root, REGISTRY_NAME)


def _fold(s: str) -> str:
    from utils.gsc_client import _fold  # import lười — module này phải load được không mạng
    return _fold(s)


def domain_of(url: str) -> str:
    """Domain thuần từ URL ('https://WWW.A.com/x:443' → 'a.com') — không đọc cfg."""
    host = urllib.parse.urlsplit(url if "://" in url else f"https://{url}").netloc
    host = host.split(":")[0].lower()
    return host[4:] if host.startswith("www.") else host


def load(base_dir: str = None) -> list[dict]:
    """Danh sách site kiểu [ {url, label, added} ]. File thiếu/hỏng → []."""
    try:
        with open(_registry_path(base_dir), encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    rows = data.get("sites") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return []
    out = []
    for r in rows:
        url = str((r or {}).get("url") or "").strip() if isinstance(r, dict) else ""
        if not url:
            continue
        out.append({"url": url,
                    "label": str((r or {}).get("label") or "").strip(),
                    "added": str((r or {}).get("added") or "")})
    return out


def save(rows: list[dict], base_dir: str = None) -> None:
    """Ghi sổ — atomic (tmp + os.replace), chuẩn hóa từng dòng trước khi ghi."""
    clean = []
    for r in rows:
        url = str((r or {}).get("url") or "").strip()
        if not url:
            continue
        clean.append({"url": url,
                      "label": str((r or {}).get("label") or "").strip(),
                      "added": str((r or {}).get("added") or "")})
    path = _registry_path(base_dir)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"sites": clean}, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def add(url: str, label: str = "", base_dir: str = None) -> tuple[bool, str]:
    """Thêm site vào sổ: khử trùng theo domain (fold không dấu) — thêm được → True.

    KHÔNG kiểm tra migrated ở đây (hàm thuần, không đụng ổ đĩa ngoài base_dir) —
    lớp CLI kiểm và đưa lời khuyên. Thêm vào sổ không tự tạo dữ liệu per-site.
    """
    url = " ".join(str(url or "").strip().split())
    if not url:
        return False, "URL trống — không có gì được thêm."
    dom = domain_of(url)
    # domain phải có ít nhất 1 chữ số/chữ (a-z0-9) — '---' hay '...' chỉ là slug rỗng
    if not dom or not any(c.isalnum() for c in dom):
        return False, ERROR_NOT_URL

    rows = load(base_dir)
    for r in rows:
        if _fold(domain_of(r["url"])) == _fold(dom):
            return False, ERROR_DUPLICATE
    rows.append({"url": url, "label": label or "", "added": date.today().isoformat()})
    save(rows, base_dir)
    return True, f"Đã thêm '{dom}' vào sổ site (tổng {len(rows)} site)."


def remove(url: str, base_dir: str = None) -> tuple[bool, str]:
    """Xóa site khỏi SỔ — dữ liệu data/<slug>/ vẫn nguyên (dữ liệu thật ở đó)."""
    dom = domain_of(url)
    if not dom or not any(c.isalnum() for c in dom):
        return False, ERROR_NOT_URL
    rows = load(base_dir)
    keep = [r for r in rows if _fold(domain_of(r["url"])) != _fold(dom)]
    if len(keep) == len(rows):
        return False, f"'{dom}' không có trong sổ — bỏ qua."
    save(keep, base_dir)
    return True, f"Đã xóa '{dom}' khỏi sổ (dữ liệu data/ vẫn nguyên — tự bạn quyết)."


def list_text(rows: list = None, migrated_slugs: list = None) -> str:
    """(Bản text của `--sites`) — sổ rỗng → hướng dẫn lệnh cần chạy, không nói dối."""
    if rows is None:
        rows = load()
    migrated_slugs = set(migrated_slugs or [])
    if not rows:
        return ("  Sổ site trống — thêm site đã migrate:\n"
                '  python main.py --site-add "https://web-cua-ban.com"\n'
                "  Xem site nào DỮ LIỆU đã tách riêng: --sites (bảng dưới đây đối chiếu giúp)")
    lines = [f"  SỔ SITE ({len(rows)} site)", "  " + "-" * 68,
             f"  {'URL':<36}{'D.Liệu tách':>12}  Nhãn"]
    for r in rows:
        dom = domain_of(r["url"])
        slug = sp.slugify_domain(dom)
        mark = "✓" if slug in migrated_slugs else "✗"
        lines.append(f'  {r["url"][:36]:<36}{mark:>12}  {r["label"][:28]}')
    lines.append("  ✓ = data/<slug>/.migrated có (F10 đã tách dữ liệu — chạy --site <url> là nòi).")
    lines.append("  ✗ = sổ có nhưng dữ liệu chưa tách — chạy --site <url> --migrate-multi-site.")
    return "\n".join(lines)


# ─── CLI ─────────────────────────────────────────────────────────────────────


def run_sites_cli() -> int:
    """Entry `--sites`: in sổ + đối chiếu trạng thái migrate từ known_site_slugs()."""
    print("=" * 76)
    print(f"  SỔ SITE — site đang làm việc: {sp.site_domain() or '(chưa cấu hình)'}")
    print("=" * 76)
    print(list_text(load(), sp.known_site_slugs()))
    print("=" * 76)
    return 0


def run_site_add_cli(url: str, label: str = "") -> int:
    """Entry `--site-add`: thêm vào sổ + nhắc migrate nếu site chưa tách dữ liệu."""
    if not url:
        print('[SiteAdd] Cách dùng: python main.py --site-add "https://web.com" [--site <url>]')
        return 2
    ok, msg = add(url, label)
    if not ok:
        print(f"[SiteAdd] {msg}")
        return 2
    dom = domain_of(url)
    if sp.slugify_domain(dom) in sp.known_site_slugs():
        print(f"[SiteAdd] ✅ {msg} — dữ liệu đã tách riêng (F10).")
    else:
        print(f"[SiteAdd] {msg}")
        print(f"[SiteAdd] ⚠️  '{dom}' CHƯA migrate — sổ có tên nhưng dữ liệu vẫn chung flat-file.")
        print(f'[SiteAdd]     Tách riêng: python main.py --site "{dom}" --migrate-multi-site')
    return 0


def run_site_remove_cli(url: str) -> int:
    """Entry `--site-remove`: bỏ khỏi sổ; dữ liệu per-site không bị xóa theo."""
    if not url:
        print('[SiteRemove] Cách dùng: python main.py --site-remove "https://web.com"')
        return 2
    ok, msg = remove(url)
    print(f"[SiteRemove] {'✅' if ok else '⚠️'} {msg}")
    return 0 if ok else 2
