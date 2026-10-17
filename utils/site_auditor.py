"""
utils/site_auditor.py — F6: crawler + bộ rule on-page cho `python main.py --audit`.

Ba lớp của F6 (docs/superpowers/plans/2026-10-13-f6-site-audit.md):
    html_probe (HTML -> dict, thuần) -> site_auditor (rule + crawl) -> CLI/GUI/CSV

Nguyên tắc không được phá:
- Chỉ request domain mục tiêu. Link ngoài domain không bao giờ được fetch — kể cả
  khi nó xuất hiện trong sitemap.xml hay khi trang đích redirect ra ngoài.
- Rule không gọi network: `audit_html(url, html)` nhận HTML string; crawler chỉ gom.
- HTTP 404/5xx/timeout là DỮ LIỆU (một finding), không phải crash; một trang nổ
  không được dừng cả đợt.
- robots.txt được tôn trọng, tự parse theo quy tắc Google (đường dẫn khớp DÀI NHẤT
  thắng, bằng độ dài thì dòng khai báo trước thắng). `urllib.robotparser` 3.11 khớp
  theo thứ tự khai báo nên `Disallow: /wp-admin/` ăn đè `Allow` dài hơn — đã đo.
"""
import json
import os
import re
from collections import deque
from datetime import datetime
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests

import config.settings as cfg
from utils import site_paths
from utils.html_probe import probe

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SEVERITY_ORDER = ("CAO", "TRUNG BÌNH", "THẤP")

TITLE_MIN = 30                      # dưới ngưỡng: chưa đủ thông tin cho CTR
TITLE_MAX = 65                      # trên ngưỡng: Google cắt bớt
META_MAX = 165
ALT_EMPTY_MIN_WORDS = 200           # chỉ nhắc alt rỗng trên trang có nội dung thật
ALT_EMPTY_MIN_COUNT = 3
DEAD_STATUSES = (404, 410)

NON_HTTP_PREFIXES = ("mailto:", "tel:", "javascript:", "data:", "ftp:", "sms:",
                     "callto:", "whatsapp:", "blob:", "about:")
TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term",
                   "utm_content", "utm_id", "gclid", "gclsrc", "dclid", "fbclid",
                   "msclkid", "mc_eid", "ref_src"}
_LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.IGNORECASE)
_SITEMAP_INDEX_RE = re.compile(r"<sitemapindex[\s>]", re.IGNORECASE)
SITEMAP_INDEX_MAX = 10          # file sitemap con đọc tối đa / lần (1 request mỗi file)


def finding(rule: str, severity: str, url: str, detail: str = "") -> dict:
    """Shape cố định — CSV và console đều đọc đúng 4 key này."""
    return {"rule": rule, "severity": severity, "url": url, "detail": detail}


def _max_pages() -> int:
    try:
        return max(1, int(getattr(cfg, "AUDIT_MAX_PAGES", 100)))
    except (TypeError, ValueError):
        return 100


def _timeout() -> int:
    try:
        return max(1, int(getattr(cfg, "AUDIT_TIMEOUT", 10)))
    except (TypeError, ValueError):
        return 10


def _user_agent() -> str:
    return str(getattr(cfg, "AUDIT_USER_AGENT", "Mozilla/5.0")) or "Mozilla/5.0"


def _headers() -> dict:
    return {"User-Agent": _user_agent(),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "vi,en;q=0.8"}


# ─── URL: một chuẩn hóa duy nhất cho crawler VÀ rule ─────────────────────────

def _clean_query(query: str) -> str:
    if not query:
        return ""
    kept = []
    for pair in query.split("&"):
        if pair and pair.split("=", 1)[0].lower() not in TRACKING_PARAMS:
            kept.append(pair)
    return "&".join(kept)


def normalize_url(href: str, base_url: str = "") -> str:
    """href (có thể tương đối) -> URL absolute đã chuẩn hóa, '' khi không fetch được.

    Bỏ fragment, bỏ tham số tracking, gộp `/a/` với `/a`, lowercase scheme+host
    (path giữ nguyên chữ — WordPress phân biệt hoa thường ở slug trong một số cấu hình).
    """
    href = (href or "").strip()
    if not href or href.lower().startswith(NON_HTTP_PREFIXES):
        return ""
    try:
        parts = urlsplit(urljoin(base_url, href) if base_url else href)
    except ValueError:
        return ""
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return ""
    path = parts.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path,
                       _clean_query(parts.query), ""))


def _host(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower().removeprefix("www.")
    except ValueError:
        return ""


def same_host(url: str, reference: str) -> bool:
    """So host đã bỏ `www.` — `https://ex.com:443/a` vẫn là chính nó."""
    host = _host(url)
    return bool(host) and host == _host(reference)


# ─── robots.txt ──────────────────────────────────────────────────────────────

class RobotsPolicy:
    """Tự parse robots.txt: khớp dài nhất thắng, bằng độ dài thì dòng đầu thắng."""

    def __init__(self, robots_text: str = "", user_agent: str = ""):
        self.groups = _parse_robots(robots_text or "")
        self.rules = _pick_rules(self.groups, user_agent)

    def allowed(self, url: str) -> bool:
        if not self.rules:
            return True
        parts = urlsplit(url)
        path = (parts.path or "/") + (("?" + parts.query) if parts.query else "")
        best = None
        for prefix, allow in self.rules:
            if path.startswith(prefix) and (best is None or len(prefix) > len(best[0])):
                best = (prefix, allow)
        return best[1] if best else True


def _parse_robots(text: str) -> list:
    groups = []
    current = None
    for raw in text.replace("\r\n", "\n").split("\n"):
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key == "user-agent":
            if current is None or current["rules"]:
                current = {"agents": [], "rules": []}
                groups.append(current)
            current["agents"].append(value.lower())
        elif key in ("allow", "disallow") and current is not None:
            if key == "disallow" and not value:
                current["rules"].append(("", True))    # "Disallow:" trống = cho phép
            elif value:
                current["rules"].append((value, key == "allow"))
    return groups


def _pick_rules(groups: list, user_agent: str) -> list:
    ua = (user_agent or "").lower()
    wildcard = None
    for group in groups:
        for token in group["agents"]:
            if token == "*":
                wildcard = group
            elif token and ua and ua.startswith(token):
                return group["rules"]
    return wildcard["rules"] if wildcard else []


# ─── fetcher ─────────────────────────────────────────────────────────────────

def _decode(resp) -> str:
    content_type = (resp.headers.get("Content-Type") or "").lower()
    encoding = resp.encoding if "charset" in content_type else "utf-8"
    try:
        return resp.content.decode(encoding, errors="replace")
    except (LookupError, TypeError):
        return resp.content.decode("utf-8", errors="replace")


def _default_fetcher(url: str):
    """(status, html, final_url) — status 0 nghĩa là không kết nối được, không raise."""
    try:
        resp = requests.get(url, timeout=_timeout(), headers=_headers(),
                            allow_redirects=True)
    except Exception:
        return (0, "", "")
    return (int(resp.status_code or 0), _decode(resp), str(resp.url or ""))


def _meta(start_url: str) -> dict:
    return {"start_url": start_url, "host": _host(start_url), "robots_status": None,
            "robots_blocked": 0, "sitemap_status": None, "sitemap_urls": 0,
            "sitemap_submaps": 0, "sitemap_truncated": False, "sitemap_files": [],
            "offsite_skipped": 0, "stopped_at_limit": False}


def _is_sitemap_file(url: str) -> bool:
    return urlsplit(url).path.lower().endswith(".xml")


def _sitemap_locs(body: str, base: str, start: str, policy) -> list:
    """Các <loc> dùng được: cùng domain, robots cho phép, không trùng, giữ thứ tự sitemap."""
    out = []
    for loc in _LOC_RE.findall(body or ""):
        target = normalize_url(loc, base)
        if (target and same_host(target, start) and policy.allowed(target)
                and target not in out):
            out.append(target)
    return out


def _sitemap_seeds(body: str, sitemap_url: str, start: str, policy, fetcher, meta) -> list:
    """URL cần audit lấy từ /sitemap.xml.

    `<sitemapindex>` = danh sách sitemap CON (XML), không phải danh sách trang: phải đọc
    thêm từng file rồi mới có URL, và bản thân file XML không được đưa vào queue — áp rule
    on-page lên XML sẽ báo "thiếu title/H1" cho một file chưa bao giờ là trang.
    """
    locs = _sitemap_locs(body, sitemap_url, start, policy)
    if not _SITEMAP_INDEX_RE.search(body or ""):
        meta["sitemap_files"] = [sitemap_url]
        pages = locs
    else:
        subs = locs[:SITEMAP_INDEX_MAX]
        pages = []
        for sub in subs:
            meta["sitemap_submaps"] += 1
            status, text, _ = fetcher(sub)
            if status == 200:
                for url in _sitemap_locs(text or "", sub, start, policy):
                    if url not in pages:
                        pages.append(url)
        meta["sitemap_truncated"] = len(locs) > SITEMAP_INDEX_MAX
        meta["sitemap_files"] = [sitemap_url] + subs
    return [u for u in pages if not _is_sitemap_file(u)]


# ─── crawler ─────────────────────────────────────────────────────────────────

def crawl(start_url: str, max_pages=None, fetcher=None) -> dict:
    """{"pages": [Page], "meta": {...}} với Page = {"url","status","html","error"}.

    Seed: URL trong sitemap.xml trước (đúng thứ tự sitemap), rồi trang chủ nếu sitemap
    thiếu nó. Sau đó BFS theo link nội bộ. Mỗi URL request tối đa một lần.
    """
    fetcher = fetcher or _default_fetcher
    start = normalize_url(start_url, start_url)
    meta = _meta(start or (start_url or ""))
    if not start:
        return {"pages": [], "meta": meta}
    parts = urlsplit(start)
    root = f"{parts.scheme}://{parts.netloc}"
    limit = int(max_pages) if max_pages else _max_pages()
    limit = max(1, limit)

    robots_url = root + "/robots.txt"
    status, text, _ = fetcher(robots_url)
    meta["robots_status"] = status
    policy = RobotsPolicy(text if status == 200 else "", _user_agent())

    seeds = []
    sitemap_url = root + "/sitemap.xml"
    if policy.allowed(sitemap_url):
        status, body, _ = fetcher(sitemap_url)
        meta["sitemap_status"] = status
        if status == 200:
            seeds = _sitemap_seeds(body or "", sitemap_url, start, policy, fetcher, meta)
            meta["sitemap_urls"] = len(seeds)
    if start not in seeds:
        seeds.append(start)

    pages = []
    # file sitemap/robots đã đọc rồi = không phải trang: đừng fetch lại (mỗi URL tối đa
    # một lần) và đừng áp rule on-page lên XML/text chỉ vì một trang có link trỏ về.
    visited = set(meta["sitemap_files"]) | {robots_url}
    queue = deque(dict.fromkeys(seeds))
    while queue and len(pages) < limit:
        url = queue.popleft()
        if url in visited:
            continue
        visited.add(url)
        if not policy.allowed(url):
            meta["robots_blocked"] += 1
            continue
        status, html, final = fetcher(url)
        page = {"url": url, "status": status, "html": html, "error": ""}
        if status == 0:
            page["error"] = "Không kết nối được (timeout hoặc lỗi mạng)"
        elif final and not same_host(final, start):
            page["error"] = f"Redirect ra ngoài domain mục tiêu: {final}"
        elif final:
            landing = normalize_url(final, url)
            if landing and landing != url:
                page["redirected_to"] = landing
                visited.add(landing)
        pages.append(page)
        if page["error"] or status != 200:
            continue
        for link in probe(html)["links"]:
            target = normalize_url(link["href"], url)
            if not target:
                continue
            if not same_host(target, start):
                meta["offsite_skipped"] += 1
                continue
            if target not in visited:
                queue.append(target)

    meta["stopped_at_limit"] = bool(queue)
    return {"pages": pages, "meta": meta}


# ─── rules: từng trang ───────────────────────────────────────────────────────

def _r_title_missing(page, d):
    if d["title"]:
        return []
    return [finding("thiếu title", "CAO", page["url"],
                    "Thẻ <title> trống hoặc không tồn tại — SERP sẽ hiển thị URL thô")]


def _r_title_length(page, d):
    size = len(d["title"])
    if not size or TITLE_MIN <= size <= TITLE_MAX:
        return []
    if size > TITLE_MAX:
        return [finding("độ dài title", "THẤP", page["url"],
                        f"title {size} ký tự (> {TITLE_MAX}) — Google sẽ cắt bớt")]
    return [finding("độ dài title", "THẤP", page["url"],
                    f"title {size} ký tự (< {TITLE_MIN}) — chưa đủ dữ liệu cho CTR")]


def _r_meta_missing(page, d):
    if d["meta_description"]:
        return []
    return [finding("thiếu meta description", "CAO", page["url"],
                    "Không có <meta name=\"description\"> — Google tự viết snippet")]


def _r_meta_length(page, d):
    size = len(d["meta_description"])
    if size <= META_MAX:
        return []
    return [finding("meta description quá dài", "THẤP", page["url"],
                    f"{size} ký tự (> {META_MAX}) — phần đuôi bị cắt trên SERP")]


def _r_h1_missing(page, d):
    if d["h1"]:
        return []
    return [finding("thiếu H1", "CAO", page["url"], "Trang không có <h1> nào")]


def _r_h1_multiple(page, d):
    if len(d["h1"]) < 2:
        return []
    shown = " | ".join(h[:40] for h in d["h1"][:3])
    return [finding("nhiều H1", "TRUNG BÌNH", page["url"],
                    f"{len(d['h1'])} thẻ h1: {shown}")]


def _r_heading_skip(page, d):
    skips = []
    previous = None
    for level, text in d["headings"]:
        if previous is not None and level > previous + 1:
            skips.append(f"h{previous} -> h{level} ({(text or '')[:40]})")
        previous = level
    if not skips:
        return []
    return [finding("heading nhảy cấp", "TRUNG BÌNH", page["url"],
                    f"{len(skips)} chỗ nhảy cấp: " + "; ".join(skips[:3]))]


def _r_img_alt_missing(page, d):
    missing = [img["src"] for img in d["images"] if img["alt"] is None]
    if not missing:
        return []
    shown = ", ".join((src or "(không có src)") for src in missing[:3])
    more = ", ..." if len(missing) > 3 else ""
    return [finding("ảnh thiếu alt", "TRUNG BÌNH", page["url"],
                    f"{len(missing)} ảnh không có attribute alt: {shown}{more}")]


def _r_img_alt_empty(page, d):
    empties = [img["src"] for img in d["images"] if img["alt"] == ""]
    if len(empties) < ALT_EMPTY_MIN_COUNT or d["word_count"] < ALT_EMPTY_MIN_WORDS:
        return []
    return [finding("alt rỗng hàng loạt", "THẤP", page["url"],
                    f"{len(empties)} ảnh dùng alt=\"\" trên trang {d['word_count']} từ"
                    " — kiểm tra ảnh mang nội dung, alt rỗng chỉ đúng cho ảnh trang trí")]


def _r_canonical_missing(page, d):
    if d["canonical"]:
        return []
    return [finding("thiếu canonical", "THẤP", page["url"],
                    "Không có <link rel=\"canonical\"> — tham số/trailing slash dễ tạo trang trùng")]


def _r_canonical_suspicious(page, d):
    raw = d["canonical"]
    if not raw:
        return []
    target = normalize_url(raw, page["url"])
    problems = []
    if not target:
        problems.append(f"không phân tích được URL: {raw}")
    else:
        if not same_host(target, page["url"]):
            problems.append(f"trỏ ra ngoài domain: {target}")
        if target.startswith("http://"):
            problems.append("dùng http:// thay vì https://")
    if not problems:
        return []
    return [finding("canonical đáng ngờ", "CAO", page["url"], "; ".join(problems))]


def _r_noindex(page, d):
    if not d["noindex"]:
        return []
    return [finding("noindex", "CAO", page["url"],
                    "<meta name=\"robots\"> chứa noindex — Google sẽ không chỉ mục trang này")]


def _r_internal_http_link(page, d):
    hits = []
    for link in d["links"]:
        target = normalize_url(link["href"], page["url"])
        if target.startswith("http://") and same_host(target, page["url"]):
            hits.append(target)
    if not hits:
        return []
    shown = ", ".join(hits[:3]) + (", ..." if len(hits) > 3 else "")
    return [finding("link http nội bộ", "TRUNG BÌNH", page["url"],
                    f"{len(hits)} link nội bộ dùng http:// (thừa một bước redirect): {shown}")]


def _r_lang_missing(page, d):
    if d["lang"]:
        return []
    return [finding("thiếu lang", "THẤP", page["url"],
                    "<html> không có attribute lang — Google phải tự đoán ngôn ngữ")]


PAGE_RULES = (_r_title_missing, _r_title_length, _r_meta_missing, _r_meta_length,
              _r_h1_missing, _r_h1_multiple, _r_heading_skip, _r_img_alt_missing,
              _r_img_alt_empty, _r_canonical_missing, _r_canonical_suspicious,
              _r_noindex, _r_internal_http_link, _r_lang_missing)


def audit_html(url: str, html: str) -> list:
    """Chạy toàn bộ rule trên một trang HTML — không network, không IO."""
    page = {"url": url, "status": 200, "html": html, "error": ""}
    d = probe(html)
    findings = []
    for rule in PAGE_RULES:
        findings += rule(page, d)
    return findings


# ─── rules: cả đợt crawl ─────────────────────────────────────────────────────

def _ok_pages(result):
    return [p for p in result["pages"] if not p.get("error") and p["status"] == 200]


def _internal_targets(result):
    """(url_trang_chứa_link, url_đích) cho mọi link nội bộ của trang đọc được."""
    out = []
    for page in _ok_pages(result):
        for link in result["probes"][page["url"]]["links"]:
            target = normalize_url(link["href"], page["url"])
            if target:
                out.append((page["url"], target))
    return out


def _r_unreadable_pages(result):
    out = []
    for page in result["pages"]:
        if page.get("error"):
            out.append(finding("không đọc được trang", "CAO", page["url"], page["error"]))
        elif page["status"] >= 500:
            out.append(finding("không đọc được trang", "CAO", page["url"],
                               f"HTTP {page['status']} — server lỗi"))
    return out


def _r_broken_internal_links(result):
    status_by = {p["url"]: p["status"] for p in result["pages"]}
    dead = {url for url, status in status_by.items() if status in DEAD_STATUSES}
    out = []
    seen = set()
    for source, target in _internal_targets(result):
        if target in dead and (source, target) not in seen:
            seen.add((source, target))
            out.append(finding("link nội bộ hỏng", "CAO", source,
                               f"{target} trả về HTTP {status_by[target]}"))
    return out


def _r_dead_pages(result):
    referenced = {target for _, target in _internal_targets(result)}
    out = []
    for page in result["pages"]:
        if page["status"] in DEAD_STATUSES and page["url"] not in referenced:
            out.append(finding("trang chết (404/410)", "CAO", page["url"],
                               f"HTTP {page['status']} — không có link nội bộ nào trỏ tới,"
                               " thường còn sót trong sitemap"))
    return out


def _r_duplicate_titles(result):
    by_title = {}
    for page in _ok_pages(result):
        title = result["probes"][page["url"]]["title"]
        if title:
            by_title.setdefault(title, []).append(page["url"])
    out = []
    for title, urls in by_title.items():
        if len(urls) < 2:
            continue
        shown = ", ".join(urls[1:4]) + (", ..." if len(urls) > 4 else "")
        out.append(finding("title trùng", "TRUNG BÌNH", urls[0],
                           f"'{title[:60]}' dùng cho {len(urls)} trang: {shown}"))
    return out


def _r_sitemap_missing(result):
    status = result["meta"].get("sitemap_status")
    if status is None or status == 200:
        return []        # None = robots chặn nên chưa từng xin, không đổ lỗi được
    return [finding("thiếu sitemap.xml", "THẤP", result["meta"]["start_url"],
                    f"/sitemap.xml trả về HTTP {status} — Google khó phát hiện trang mới")]


def _r_robots_blocked(result):
    blocked = result["meta"].get("robots_blocked") or 0
    if not blocked:
        return []
    return [finding("robots.txt chặn", "THẤP", result["meta"]["start_url"],
                    f"{blocked} URL bị robots.txt chặn, không audit")]


SUITE_RULES = (_r_unreadable_pages, _r_broken_internal_links, _r_dead_pages,
               _r_duplicate_titles, _r_sitemap_missing, _r_robots_blocked)

RULE_COUNT = len(PAGE_RULES) + len(SUITE_RULES)


def audit_crawl(result: dict) -> list:
    """Toàn bộ finding của một đợt crawl: rule từng trang + rule so sánh giữa các trang."""
    pages = result["pages"]
    meta = result.get("meta") or _meta(pages[0]["url"] if pages else "")
    probes = {}
    findings = []
    for page in _ok_pages({"pages": pages, "meta": meta}):
        d = probe(page["html"])
        probes[page["url"]] = d
        for rule in PAGE_RULES:
            findings += rule(page, d)
    ctx = {"pages": pages, "meta": meta, "probes": probes}
    for rule in SUITE_RULES:
        findings += rule(ctx)
    return findings


# ─── state: kết quả audit gần nhất (để --export audit đọc lại) ───────────────

def _state_path() -> str:
    """data/audit_last.json — đi qua MỘT hàm; F10 rẽ sang data/<site>/ khi đã migrate."""
    return site_paths.per_site("audit_last.json",
                               os.path.join(ROOT, getattr(cfg, "AUDIT_STATE_DIR", "data")))


def save_last_audit(findings: list, url: str = "", pages: int = 0) -> str:
    """Lưu findings của lần audit vừa xong. Chỉ 4 key của finding — không chứa HTML."""
    payload = {
        "url": url,
        "pages": pages,
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "findings": [{key: f.get(key, "") for key in ("rule", "severity", "url", "detail")}
                     for f in findings],
    }
    path = _state_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    # Write-then-rename: audit có thể bị Ctrl-C giữa lúc ghi, JSON cụt làm load_last_audit()
    # trả [] im lặng → --export audit ra file chỉ có tiêu đề mà không ai biết vì sao.
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
    return path


def load_last_audit() -> list:
    """findings lần audit gần nhất — file thiếu/hỏng/rác thì trả [] (không raise)."""
    try:
        with open(_state_path(), encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return []
    out = []
    for f in (raw.get("findings") or []) if isinstance(raw, dict) else []:
        if not isinstance(f, dict):
            continue
        severity = f.get("severity")
        if severity not in SEVERITY_ORDER or not f.get("rule") or not f.get("url"):
            continue
        out.append(finding(str(f["rule"]), str(severity), str(f["url"]),
                           str(f.get("detail") or "")))
    return out


# ─── output ──────────────────────────────────────────────────────────────────

def audit_rows(findings: list):
    """(header, rows) cho exporter — sắp xếp CAO trước, rồi rule, rồi URL."""
    order = {severity: index for index, severity in enumerate(SEVERITY_ORDER)}
    ranked = sorted(findings, key=lambda f: (order.get(f["severity"], len(order)),
                                             f["rule"], f["url"]))
    header = ["severity", "rule", "url", "detail"]
    return header, [[f["severity"], f["rule"], f["url"], f["detail"]] for f in ranked]


def _print_findings(findings: list) -> None:
    for severity in SEVERITY_ORDER:
        group = [f for f in findings if f["severity"] == severity]
        if not group:
            continue
        print(f"\n── {severity} ({len(group)}) ──")
        for f in group:
            print(f"  [{f['rule']}] {f['url']} — {f['detail']}")


def _sitemap_note(meta: dict) -> str:
    status = meta.get("sitemap_status")
    if status is None:
        return "không xin được (robots chặn)"
    if status != 200:
        return f"HTTP {status}"
    if meta.get("sitemap_submaps"):
        note = (f"{meta['sitemap_submaps']} sitemap con → "
                f"{meta.get('sitemap_urls', 0)} URL cùng domain")
        if meta.get("sitemap_truncated"):
            note += f" (chỉ đọc {SITEMAP_INDEX_MAX} file sitemap con đầu)"
        return note
    return f"{meta.get('sitemap_urls', 0)} URL cùng domain"


def _robots_note(meta: dict) -> str:
    status = meta.get("robots_status")
    if status is None or status != 200:
        return "không có (coi như cho phép)"
    blocked = meta.get("robots_blocked") or 0
    return f"tôn trọng, {blocked} URL bị chặn" if blocked else "tôn trọng, không chặn URL nào"


def run_audit_cli(limit=None, fetcher=None, url: str = "") -> int:
    """Entry `--audit`: crawl rồi in báo cáo theo nhóm severity. Trả exit code."""
    start = (url or getattr(cfg, "TARGET_URL", "") or "").strip()
    if not start:
        print("[Audit] ⚠️ Chưa đặt TARGET_URL trong config/settings.py — không biết audit site nào.")
        return 2
    if limit is not None:
        try:
            limit = int(str(limit).strip())
        except (TypeError, ValueError):
            print(f"[Audit] ⚠️ --audit-limit phải là số nguyên >= 1 (nhận '{limit}').")
            return 2
        if limit < 1:
            print(f"[Audit] ⚠️ --audit-limit phải là số nguyên >= 1 (nhận '{limit}').")
            return 2

    print(f"[Audit] Crawl {start} — tối đa {limit or _max_pages()} trang,"
          f" {_timeout()}s/trang, chỉ cùng domain")
    result = crawl(start, limit, fetcher)
    meta = result["meta"]
    print(f"[Audit] sitemap.xml: {_sitemap_note(meta)} | robots.txt: {_robots_note(meta)}")

    findings = audit_crawl(result)
    if not _ok_pages(result):
        print("[Audit] ❌ Không đọc được trang nào — kiểm tra TARGET_URL và kết nối mạng.")
        return 1

    _print_findings(findings)
    save_last_audit(findings, url=start, pages=len(result["pages"]))
    counts = {severity: sum(1 for f in findings if f["severity"] == severity)
              for severity in SEVERITY_ORDER}
    print(f"\n[Audit] {len(result['pages'])} trang / {len(findings)} lỗi"
          f" (CAO {counts['CAO']}, TRUNG BÌNH {counts['TRUNG BÌNH']}, THẤP {counts['THẤP']})")
    if not findings:
        print("[Audit] ✅ Không tìm thấy lỗi trong các rule đã cài.")
    print("[Audit] 💾 Đã lưu kết quả — mở bằng Excel: python main.py --export audit")
    if meta.get("stopped_at_limit"):
        print(f"[Audit] ℹ️ Dừng ở ngưỡng {limit or _max_pages()} trang — còn link chưa đi hết;"
              " tăng bằng --audit-limit N.")
    return 0
