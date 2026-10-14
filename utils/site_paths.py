"""
utils/site_paths.py — Một điểm sinh đường dẫn per-site cho F10 (multi-site).

Ý định: mọi module đọc/ghi state (rank/gsc/session/keywords) gọi vào đây thay vì
hard-code path. Chưa migrate → trả về đường dẫn flat cũ ở gốc project (đơn site
chạy y hệt hôm nay). Sau khi `--migrate-multi-site` tạo `data/<slug>/` → rẽ sang per-site.

    site_slug()      -> 'nankybeauty-com'         # slug từ cfg.TARGET_URL lúc gọi
    is_multi_site()  -> bool                       # data/<slug>/ đã tồn tại chưa
    site_file(name)  -> data/<slug>/<name> hoặc <FLAT_ROOT>/<name>
    site_config(name)-> config/<slug>/<name> hoặc <CONFIG_ROOT>/<name>
    report_prefix()  -> '<slug>_' khi multi-site, '' khi đơn site

Quyết định đã chốt (spec F10): slug tự sinh từ domain (không SITE_ID) · fallback flat-file
(không breaking) · profile browser dùng chung theo persona (KHÔNG scope per-site) · lock chung.

Chỉ stdlib. Không import keywords/gsc (tránh vòng import — keywords sẽ import lại module này).
DATA_ROOT/CONFIG_ROOT/FLAT_ROOT để ở mức module (override được cho test) như các hằng số path khác.
"""
import os
import re
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Gốc chứa file state per-site (data/<slug>/) — tách để test trỏ sang temp dir
DATA_ROOT = os.path.join(ROOT, "data")
# Gốc chứa config per-site (config/<slug>/) và file config flat cũ
CONFIG_ROOT = os.path.join(ROOT, "config")
# Gốc chứa flat-file legacy (rank_history.json ở gốc project) — nơi fallback trỏ về
FLAT_ROOT = ROOT


def _domain() -> str:
    """netloc từ cfg.TARGET_URL, bỏ scheme/port/path/www — 'https://WWW.A.com/x:443' → 'a.com'."""
    import config.settings as cfg
    url = getattr(cfg, "TARGET_URL", "") or ""
    host = urlparse(url).netloc or url          # có scheme → netloc; không → cả chuỗi
    host = host.split("/")[0]                    # cắt path khi chuỗi thô còn '/blog'
    host = host.lower().split(":")[0].strip()    # cắt port
    return host[4:] if host.startswith("www.") else host


def site_slug() -> str:
    """Slug folder từ domain mục tiêu; ký tự ngoài [a-z0-9] gộp thành '-'. Domain rỗng → ''."""
    slug = re.sub(r"[^a-z0-9]+", "-", _domain()).strip("-")
    return slug


def site_domain() -> str:
    """Domain thuần của cfg.TARGET_URL ('nankybeauty.com') — cho CLI --site suy GSC property."""
    return _domain()


def known_site_slugs() -> list[str]:
    """Các site đã migrate = thư mục con trong data/ (data/<slug>/). Rỗng nếu DATA_ROOT chưa có."""
    if not os.path.isdir(DATA_ROOT):
        return []
    return sorted(
        d for d in os.listdir(DATA_ROOT)
        if os.path.isdir(os.path.join(DATA_ROOT, d)) and not d.startswith(".")
    )


def _site_data_dir() -> str:
    return os.path.join(DATA_ROOT, site_slug())


def is_multi_site() -> bool:
    """Bật per-site khi và khi chỉ data/<slug>/ tồn tại (do --migrate-multi-site tạo)."""
    slug = site_slug()
    return bool(slug) and os.path.isdir(_site_data_dir())


def site_file(name: str) -> str:
    """File state: data/<slug>/<name> nếu đã migrate, ngược lại flat <FLAT_ROOT>/<name>."""
    if is_multi_site():
        return os.path.join(_site_data_dir(), name)
    return os.path.join(FLAT_ROOT, name)


def site_config(name: str) -> str:
    """File config per-site: cùng tín hiệu is_multi_site (đơn vị bật/tắt là cả site)."""
    if is_multi_site():
        return os.path.join(CONFIG_ROOT, site_slug(), name)
    return os.path.join(CONFIG_ROOT, name)


def report_prefix() -> str:
    """Tiền tố tên file báo cáo: '<slug>_' khi multi-site, '' khi đơn site (giữ nguyên F1)."""
    return f"{site_slug()}_" if is_multi_site() else ""


def per_site(name: str, base_dir: str) -> str:
    """File state nằm trong một base dir tự quản (data/, config/...).

    Multi-site → <base_dir>/<slug>/<name>; đơn site → <base_dir>/<name> (y như hôm nay).
    Khác site_file(): site_file fallback về FLAT_ROOT (gốc project) cho rank/gsc/session legacy;
    per_site giữ nguyên base_dir cũ của module (alerts/scheduler/backlinks/audit/pagespeed vốn
    đã nằm trong data/, không ở gốc) — đơn vị bật/tắt vẫn là is_multi_site().
    """
    if is_multi_site():
        return os.path.join(base_dir, site_slug(), name)
    return os.path.join(base_dir, name)
