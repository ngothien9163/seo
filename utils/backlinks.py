"""
utils/backlinks.py — F7: danh sách backlink của site + máy verify THUẦN một trang.

Hai chuyện tách bạch, hay bị nhầm làm một:
  * `backlinks/tracker.py` = CƠ HỘI đặt link (nền tảng chưa gõ, chưa có gì trên mạng).
  * module này = link owner đã thật sự đặt, ghi trong `config/backlinks.json`
    (thêm tay bằng --backlink-add, hoặc import CSV "External links" của Search
    Console). Không có link nào tự sinh ra cả.

Verify: `verify_page(url, html, status, domain)` nhìn HTML tĩnh của MỘT trang và trả
lời — trang còn sống không, có `<a href>` trỏ về domain mình không (tính cả subdomain,
không tính tên gần giống), dofollow hay nofollow/sponsored/ugc, anchor text là gì.
Tái dùng `utils/html_probe.py` của F6 — stdlib `html.parser`, không thêm dependency.

Fetch thật (network) nằm ở `utils/backlink_checker.py`; xuất CSV nằm ở
`utils/exporter.py`. Module này chỉ stdlib ở đầu file — CLI/GUI/importer import nó
mà không được kéo theo `requests` hay `playwright`.
"""
import json
import os
from datetime import datetime, timedelta
from urllib.parse import urlparse, urljoin

import config.settings as cfg
from utils import site_paths
from utils.html_probe import probe

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TIME_FMT = "%Y-%m-%d %H:%M:%S"

# rel="nofollow" là chuẩn; Google còn hai giá trị cùng nhóm "không chuyển uy tín".
_NON_TRANSFER_REL = ("nofollow", "sponsored", "ugc")
# Tham số tracking: cùng một trang vẫn bị tính là hai link nếu để nguyên URL.
_TRACKING_PREFIXES = ("utm_", "piwik_", "matomo_")
_TRACKING_PARAMS = {"gclid", "gbraid", "wbraid", "fbclid", "ref", "ref_src",
                    "mc_eid", "igshid", "source", "share"}


# ─── đường dẫn state (điểm duy nhất) ─────────────────────────────────────────


def _store_path() -> str:
    """Nơi ở của danh sách link — đọc cfg lúc gọi; F10 rẽ sang config/<site>/ khi đã migrate."""
    return site_paths.per_site(getattr(cfg, "BACKLINK_STORE_FILE", "backlinks.json"),
                               os.path.join(ROOT, "config"))


def _state_path() -> str:
    return site_paths.per_site("backlink_status.json",
                               os.path.join(ROOT, getattr(cfg, "BACKLINK_STATE_DIR", "data")))


def _now() -> str:
    return datetime.now().strftime(TIME_FMT)


# ─── domain / URL thuần ──────────────────────────────────────────────────────


def target_domain() -> str:
    """Domain mục tiêu từ cfg.TARGET_URL — 'https://WWW.Site.com/x' → 'site.com'."""
    return _norm_domain(getattr(cfg, "TARGET_URL", "") or "")


def _norm_domain(value: str) -> str:
    """Bỏ scheme/path/port/www, về chữ thường. 'https://WWW.A.vn/p' → 'a.vn'."""
    s = (value or "").strip().lower()
    if not s:
        return ""
    parsed = urlparse(s)
    raw = parsed.netloc if parsed.scheme or "@" in s else s.split("/")[0]
    host = raw.split("@")[-1].split("/")[0].split(":")[0].strip().strip(".")
    return host[4:] if host.startswith("www.") else host


def _link_host(href: str, base: str) -> str:
    """Host thật của một href nằm trên trang `base`; '' nếu không phải link http(s).

    Resolve theo trang chứa link chứ không theo domain mục tiêu — `/services` trên
    trang bên thứ ba là link nội bộ của họ, còn `//a.vn/x` là protocol-relative.
    """
    raw = (href or "").strip()
    if not raw or raw.startswith("#"):
        return ""
    parts = urlparse(urljoin(base or "", raw))
    if parts.scheme not in ("http", "https"):
        return ""
    return _norm_domain(parts.netloc)


def _points_to(host: str, target: str) -> bool:
    """Host có phải domain mục tiêu hoặc subdomain của nó — không nuốt 'target.evil.io'."""
    if not target or not host:
        return False
    return host == target or host.endswith("." + target)


def _valid_url(url) -> str:
    """URL http(s) có host hợp lệ, đã trim; ngược lại trả '' (không raise)."""
    if not isinstance(url, str):
        return ""
    raw = " ".join(url.strip().split())
    if not raw:
        return ""
    parts = urlparse(raw)
    if parts.scheme not in ("http", "https") or not _norm_domain(parts.netloc):
        return ""
    return raw


def _link_key(url: str) -> str:
    """Chìa chống trùng: bỏ scheme/fragment/tham số tracking/dấu gạch cuối.

    'https://b.vn/x?utm_source=fb' và 'https://b.vn/x/' là MỘT trang — thêm hai lần
    thì một backlink thật bị đếm thành hai dòng trong báo cáo.
    """
    raw = _valid_url(url)
    if not raw:
        return ""
    parts = urlparse(raw.lower())
    pairs = []
    for chunk in parts.query.split("&"):
        if chunk:
            name, _, value = chunk.partition("=")
            pairs.append((name, value))
    kept = [(n, v) for n, v in pairs
            if not n.startswith(_TRACKING_PREFIXES) and n not in _TRACKING_PARAMS]
    query = "&".join(f"{n}={v}" for n, v in kept)
    path = (parts.path or "/").rstrip("/")
    return f"{_norm_domain(parts.netloc)}{path}" + (f"?{query}" if query else "")


# ─── store: config/backlinks.json ────────────────────────────────────────────


def _entry_from(item) -> dict:
    """Một phần tử trong file (chuỗi hoặc dict) -> entry chuẩn; rác -> dict rỗng."""
    if isinstance(item, str):
        item = {"url": item}
    if not isinstance(item, dict):
        return {}
    url = _valid_url(item.get("url"))
    if not url:
        return {}
    entry = {"url": url,
             "note": " ".join(str(item.get("note") or "").split()),
             "added": str(item.get("added") or _now())}
    return entry


def _normalize_links(links) -> list:
    """Bỏ entry rác, gỡ trùng theo _link_key (giữ lần đầu, giữ note/added đã có)."""
    out, seen = [], set()
    for item in (links or []):
        entry = _entry_from(item)
        if not entry:
            continue
        key = _link_key(entry["url"])
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(entry)
    return out


def load_links() -> list:
    """Danh sách backlink đang theo dõi. File thiếu/hỏng -> [] (không raise)."""
    path = _store_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    if isinstance(data, list):            # tay người sửa thành list trần vẫn đọc được
        raw = data
    elif isinstance(data, dict):
        raw = data.get("links") or []
    else:
        return []
    return _normalize_links(raw if isinstance(raw, list) else [])


def save_links(links, site: str = None) -> str:
    """Ghi danh sách link (đã chuẩn hóa) — atomic qua file tạm, trả về path."""
    payload = {"site": site or target_domain(), "links": _normalize_links(links)}
    path = _store_path()
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
    return path


def add_link(url, note: str = "") -> tuple:
    """Thêm một backlink đã thật sự đặt. Trả (đã thêm chưa, thông điệp tiếng Việt)."""
    if not isinstance(url, str):
        return False, "Link phải là một chuỗi URL — không có gì được thêm."
    clean = _valid_url(url)
    if not clean:
        raw = (url or "").strip()
        if not raw:
            return False, "Link rỗng — không có gì được thêm."
        return False, (f"'{raw}' không phải URL http(s) hợp lệ — cần dạng "
                       "https://domain/trang-chua-link.")
    current = load_links()
    key = _link_key(clean)
    for existing in current:
        if _link_key(existing["url"]) == key:
            return False, f"'{clean}' đã có trong danh sách (đang lưu là '{existing['url']}')."
    entry = {"url": clean, "note": " ".join(str(note or "").split()), "added": _now()}
    save_links(current + [entry])
    return True, f"Đã thêm '{clean}' — tổng {len(current) + 1} backlink đang theo dõi."


def remove_link(url) -> tuple:
    """Bỏ một backlink khỏi danh sách theo chìa chuẩn hóa (không cần nhớ đúng dấu)."""
    key = _link_key(url if isinstance(url, str) else "")
    if not key:
        return False, "Link không hợp lệ — không có gì bị bỏ."
    current = load_links()
    kept = [e for e in current if _link_key(e["url"]) != key]
    if len(kept) == len(current):
        return False, f"'{url}' không có trong danh sách — không có gì bị bỏ."
    save_links(kept)
    return True, f"Đã bỏ '{url}' — còn {len(kept)} backlink đang theo dõi."


def _urls_in_csv(rows) -> list:
    """Mọi ô parse được thành URL http(s), giữ thứ tự gặp, đã gỡ trùng theo chìa.

    Không tìm "cột tên External link": GSC đổi tên cột theo báo cáo và theo phiên bản,
    còn giá trị URL thì nhận ra được. Ô là domain trần ("/noi-mi", "topbep.vn") bị bỏ
    vì không phải địa chỉ trang — verify một domain thì vô nghĩa.
    """
    out, seen = [], set()
    for row in (rows or []):
        for cell in (row or []):
            url = _valid_url((cell or "").strip())
            key = _link_key(url)
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(url)
    return out


def import_gsc_csv(path, note: str = "import từ CSV GSC") -> tuple:
    """Nạp CSV "External links" tải tay từ Search Console vào danh sách theo dõi.

    API của GSC **không** có endpoint external links — con đường duy nhất là UI →
    Export. Vì vậy parser chỉ tin vào hình dạng giá trị, không tin tiêu đề cột.
    Trả (số link mới thêm, thông điệp tiếng Việt). File hỏng/không có URL → thêm 0,
    danh sách cũ không bị động tới.
    """
    if not isinstance(path, str) or not path:
        return 0, "Chưa chỉ định file CSV nào — dùng: python main.py --backlink-import <duong-dan.csv>"
    if not os.path.exists(path):
        return 0, f"Không thấy file '{path}' — kiểm tra lại đường dẫn CSV tải từ Search Console."
    import csv
    try:
        with open(path, encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle))
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        return 0, f"Không đọc được file CSV ({type(exc).__name__}: {str(exc)[:120]})."

    own = target_domain()
    seen_keys = {_link_key(entry["url"]) for entry in load_links()}
    added = skipped_own = skipped_dup = 0
    for url in _urls_in_csv(rows):
        host = _norm_domain(urlparse(url).netloc)
        if own and (host == own or host.endswith("." + own)):
            skipped_own += 1          # trang của chính site không bao giờ là backlink
            continue
        key = _link_key(url)
        if key in seen_keys:
            skipped_dup += 1
            continue
        seen_keys.add(key)
        if add_link(url, note=note)[0]:
            added += 1

    if not added and not skipped_own and not skipped_dup:
        return 0, ("Không tìm thấy ô URL http(s) nào trong file — GSC có thể đổi tên cột, "
                   "hoặc đây không phải báo cáo 'External links'. Danh sách hiện tại giữ nguyên.")
    parts = [f"Đã thêm {added} backlink từ CSV GSC"]
    if skipped_dup:
        parts.append(f"bỏ {skipped_dup} URL đã có trong danh sách (trùng)")
    if skipped_own:
        parts.append(f"bỏ {skipped_own} trang của chính site {own} — không phải backlink")
    return added, ", ".join(parts) + f" — tổng {len(load_links())} link đang theo dõi."


# ─── state: data/backlink_status.json ────────────────────────────────────────


def load_state() -> dict:
    """Kết quả check lần gần nhất theo từng URL. File thiếu/hỏng -> {} (không raise)."""
    path = _state_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): v for k, v in data.items() if isinstance(v, dict) and k}


def save_state(state) -> str:
    """Ghi kết quả check — atomic, chỉ giữ entry là dict."""
    payload = {str(k): v for k, v in (state or {}).items() if isinstance(v, dict)}
    path = _state_path()
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
    return path


def is_fresh(entry, hours: float = None, now: datetime = None) -> bool:
    """Entry này còn trong cửa sổ cache? Mốc thời gian sai kiểu gì cũng = cũ."""
    if not isinstance(entry, dict):
        return False
    stamp = entry.get("checked_at")
    if not isinstance(stamp, str) or not stamp.strip():
        return False
    try:
        checked = datetime.strptime(stamp.strip(), TIME_FMT)
        window = float(cfg.BACKLINK_CACHE_HOURS if hours is None else hours)
    except (TypeError, ValueError):
        return False
    delta = (now or datetime.now()) - checked
    return timedelta(0) <= delta < timedelta(hours=window)


# ─── verify thuần một trang ──────────────────────────────────────────────────


def verify_page(url: str, html: str, status: int, domain: str,
                final_url: str = "") -> dict:
    """HTML của trang đang đặt link -> verdict, không IO và không raise.

    `url` là link owner khai báo, `final_url` là đích sau cùng sau redirect (nếu có)
    — href tương đối phải resolve theo trang THỰC SỰ đã đọc, không theo URL cũ.
    """
    target = _norm_domain(domain)
    base = final_url or url
    result = {"url": url, "final_url": base, "status": status,
              "has_link": False, "dofollow": False, "links_to_target": 0,
              "anchors": [], "rel_seen": []}
    if not html:
        return result
    for link in probe(html)["links"]:
        if not _points_to(_link_host(link.get("href", ""), base), target):
            continue
        result["has_link"] = True
        result["links_to_target"] += 1
        rel = " ".join(str(link.get("rel") or "").split()).lower()
        result["rel_seen"].append(rel)
        text = " ".join(str(link.get("text") or "").split())
        if text and text not in result["anchors"]:
            result["anchors"].append(text)
        if not any(token in _NON_TRANSFER_REL for token in rel.split()):
            result["dofollow"] = True
    return result
