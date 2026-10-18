"""
utils/site_paths.py — Một điểm sinh đường dẫn per-site cho F10 (multi-site).

Ý định: mọi module đọc/ghi state (rank/gsc/session/keywords) gọi vào đây thay vì
hard-code path. Chưa migrate → trả về đường dẫn flat cũ ở gốc project (đơn site
chạy y hệt hôm nay). Sau khi `--migrate-multi-site` chạy xong (có dấu
`data/<slug>/.migrated`) → rẽ sang per-site.

    site_slug()      -> 'nankybeauty-com'         # slug từ cfg.TARGET_URL lúc gọi
    is_multi_site()  -> bool                       # data/<slug>/.migrated đã có chưa
    site_file(name)  -> data/<slug>/<name> hoặc <FLAT_ROOT>/<name>
    site_config(name)-> config/<slug>/<name> hoặc <CONFIG_ROOT>/<name>
    report_prefix()  -> '<slug>_' khi multi-site, '' khi đơn site
    mark_migrated()  -> ghi dấu hoàn tất (bật per-site) — migrate_sites gọi ở cuối

Quyết định đã chốt (spec F10): slug tự sinh từ domain (không SITE_ID) · fallback flat-file
(không breaking) · profile browser dùng chung theo persona (KHÔNG scope per-site) · lock chung.

Dấu `.migrated` là điều kiện DUY NHẤT bật per-site — không phải "thư mục tồn tại":
migrate dựng thư mục trước rồi mới copy file, nên crash giữa chừng để lại thư mục có
mà dữ liệu thiếu; bật per-site lúc đó là chạy trên dữ liệu nửa vời (rank history chỉ
có 2/10 file). Marker chỉ được ghi khi mọi file đã copy xong, nên "có marker" ==
"dữ liệu per-site đã đủ để tự đứng một mình".

Chỉ stdlib. Không import keywords/gsc (tránh vòng import — keywords sẽ import lại module này).
DATA_ROOT/CONFIG_ROOT/FLAT_ROOT để ở mức module (override được cho test) như các hằng số path khác.
"""
import os
import re
from datetime import datetime
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Dấu HOÀN TẤT migrate trong data/<slug>/. Bật/tắt per-site chỉ dựa vào file này.
MIGRATED_MARKER = ".migrated"

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


def slugify_domain(domain: str) -> str:
    """Slug từ DOMAIN cho trước (không đọc cfg) — cùng luật site_slug() gốc:
    LOWERCASE trước (`domain.lower()` — chữ hoa thành chữ thường, không biến dấu '-'),
    rồi ký tự ngoài [a-z0-9] gộp thành '-'. Hàm thuần để site_registry đối chiếu
    sổ ↔ slug migrate: 'NankyBeauty.com' → 'nankybeauty-com' (regex cũ dính 'N','B'
    trực tiếp thì tụt chữ hoá thành 'anky-eauty-com' — lệch folder đã migrate)."""
    return re.sub(r"[^a-z0-9]+", "-", (domain or "").lower()).strip("-")


def site_slug() -> str:
    """Slug folder từ domain mục tiêu; ký tự ngoài [a-z0-9] gộp thành '-'. Domain rỗng → ''."""
    return slugify_domain(_domain())


def site_domain() -> str:
    """Domain thuần của cfg.TARGET_URL ('nankybeauty.com') — cho CLI --site suy GSC property."""
    return _domain()


def known_site_slugs() -> list[str]:
    """Các site đã migrate XONG = thư mục con của data/ có dấu .migrated. Rỗng nếu DATA_ROOT chưa có."""
    if not os.path.isdir(DATA_ROOT):
        return []
    return sorted(
        d for d in os.listdir(DATA_ROOT)
        if os.path.isdir(os.path.join(DATA_ROOT, d)) and not d.startswith(".")
        and is_migrated_dir(os.path.join(DATA_ROOT, d))
    )


def _site_data_dir() -> str:
    return os.path.join(DATA_ROOT, site_slug())


def is_migrated_dir(path: str) -> bool:
    """Thư mục site này đã migrate xong chưa — có dấu .migrated bên trong."""
    return os.path.isfile(os.path.join(path, MIGRATED_MARKER))


def mark_migrated(slug: str = "") -> str:
    """Ghi dấu HOÀN TẤT migrate cho site (atomic) → bật per-site. Trả đường dẫn marker.

    Chỉ gọi khi MỌI file đã copy xong: dấu này là thứ duy nhất khiến is_multi_site()
    trả True, ghi sớm là tự bắn vào chân (xem giải thích ở docstring đầu file).
    """
    slug = slug or site_slug()
    if not slug:
        raise ValueError("slug rỗng — không có site nào để đánh dấu migrate")
    folder = os.path.join(DATA_ROOT, slug)
    os.makedirs(folder, exist_ok=True)
    marker = os.path.join(folder, MIGRATED_MARKER)
    tmp = marker + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(f"{slug} {datetime.now().isoformat(timespec='seconds')}\n")
        os.replace(tmp, marker)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
    return marker


def is_multi_site() -> bool:
    """Bật per-site khi và khi chỉ data/<slug>/.migrated tồn tại (do --migrate-multi-site ghi).

    Thư mục trần KHÔNG đủ: xem giải thích dấu .migrated ở docstring đầu file.
    """
    slug = site_slug()
    return bool(slug) and is_migrated_dir(_site_data_dir())


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
