# -*- coding: utf-8 -*-
"""utils/internal_links.py — P1-2: gợi ý link nội bộ từ dữ liệu đã có.

Bài mới về từ khóa X nên link tới bài cũ nào? Gợi ý bằng cách:
1. Gom URL trang của site: từ audit gần nhất + URL của chính site lưu trong
   rank history (trang đã từng xếp hạng) + trang chủ. KHÔNG crawl lại —
   chạy `--audit` hoặc `--rank` trước thì gợi ý càng nhiều.
2. Với mỗi từ khóa đang theo dõi: tìm 2 trang khớp token tốt nhất
   (≥ MIN_LINK_HITS token riêng) → gợi ý một trang khác link chéo qua cùng từ khóa.

Matching và fold/stopword dùng lại từ utils.audit_actions — sau mỗi thay đổi
token, chỉ một nơi cần sửa. Không mạng, không ghi file gì.
"""
from urllib.parse import urlsplit

from utils import audit_actions as aa

MIN_LINK_HITS = 2   # URL cần chạm >= N token riêng của từ khóa mới tính là "đúng bài"


def _norm_path(url: str) -> str:
    """URL → path sạch để gộp trùng ('/blog/a' == '/blog/a/')."""
    try:
        parts = urlsplit(str(url or ""))
        path = parts.path or "/"
    except ValueError:
        path = "/"
    return path.rstrip("/") or "/"


def _same_site(url: str, target: str) -> bool:
    try:
        h1 = (urlsplit(str(url)).hostname or "").lower().removeprefix("www.")
        h2 = (urlsplit(str(target)).hostname or "").lower().removeprefix("www.")
    except ValueError:
        return False
    return bool(h1) and h1 == h2


def collect_pages(target_url: str = "", audit_findings=None, rank_urls=None) -> list[str]:
    """Trang của site để làm ứng viên: audit + rank + trang chủ, gộp trùng theo path.

    audit_findings: list finding (lấy f["url"]); rank_urls: list URL lưu trong
    rank history (lọc chỉ giữ URL cùng site). Trang đầu tiên giữ nguyên thứ tự
    (trang chủ trước nếu target_url có), thứ tự ổn định giúp gợi ý tái lập.
    """
    out, seen = [], set()
    target_url = str(target_url or "").strip()
    if target_url:
        p = _norm_path(target_url)
        if p not in seen:
            seen.add(p)
            out.append(target_url)
    for f in (audit_findings or []):
        url = str((f or {}).get("url", "") if isinstance(f, dict) else f)
        if not url:
            continue
        p = _norm_path(url)
        if p not in seen:
            seen.add(p)
            out.append(url)
    for url in (rank_urls or []):
        url = str(url or "")
        if not url or not _same_site(url, target_url):
            continue
        p = _norm_path(url)
        if p not in seen:
            seen.add(p)
            out.append(url.split("?")[0].split("#")[0])
    return out


def rank_urls_from_history(history: dict) -> list[str]:
    """URL của CHÍNH site lưu trong rank history ({checks: {stamp: {kw: {pos,url}}}}
    → list URL, gần nhất trước, bỏ None/rỗng."""
    out, seen = [], set()
    for stamp in sorted((history.get("checks") or {}).keys(), reverse=True):
        for kw_entry in (history["checks"][stamp] or {}).values():
            url = str((kw_entry or {}).get("url") or "")
            if not url or url in seen:
                continue
            seen.add(url)
            out.append(url)
    return out


def _match_pages(keyword: str, pages: list[str]) -> list[tuple[str, int]]:
    """URLs khớp từ khóa: (path, hits) với hits >= MIN_LINK_HITS, hits giảm dần.

    hits đếm token RIÊNG của từ khóa xuất hiện trong path — tổng token thường
    dùng ('mi') không phân biệt hai bài khác nhau, token riêng mới cho biết
    'đúng bài này nói về từ khóa đó'.
    """
    ktoks = aa._kw_tokens(keyword)
    if len(ktoks) < MIN_LINK_HITS:
        return []   # từ khóa ≤1 token không đủ chia để phân biệt trang
    scored = []
    for page in pages or []:
        ptoks = set(aa._url_tokens(_norm_path(page)))
        distinct = len({t for t in ktoks if t in ptoks})
        total = sum(1 for t in ktoks if t in ptoks)
        if distinct < MIN_LINK_HITS:
            continue
        scored.append((page.rstrip("/"), (distinct, total)))
    seen, ordered = set(), []
    for page, score in sorted(scored, key=lambda kv: (-kv[1][0], -kv[1][1], kv[0])):
        if page in seen:
            continue
        seen.add(page)
        ordered.append((page, score[0]))
    return ordered


def build_suggestions(keywords: list, pages: list[str],
                      limit: int = 10) -> list[dict]:
    """Mỗi từ khóa tối đa 1 gợi ý: trang khớp nhất (nhận link nội) + trang nhì
    (nguồn link tới). Trả sorted theo số token trùng giảm (cụ thể trước)."""
    suggestions = []
    for kw in keywords or []:
        matches = _match_pages(kw, pages)
        if len(matches) < 2:
            continue
        first, _ = matches[0]
        second, _ = matches[1]
        suggestions.append({"keyword": kw, "page": first, "link_from": second,
                            "hits": matches[0][1]})
    suggestions.sort(key=lambda s: (-s["hits"], s["keyword"]))
    return suggestions[:max(int(limit), 0)]


def suggestions_text(suggestions: list, source_note: str = "") -> str:
    if not suggestions:
        return ("  Chưa gợi ý được link nội bộ nào — cần audit/rank đã chạy và "
                "từ khóa ≥ 2 token trùng với URL trang.\n"
                "  Chạy python main.py --audit hoặc --rank trước, rồi --internal-links.")
    lines = ["  GỢI Ý LINK NỘI BỘ — mỗi từ khóa: bài khớp nhất + trang nên link tới nó"]
    if source_note:
        lines.append(f"  ({source_note})")
    lines.append("  " + "-" * 72)
    for s in suggestions:
        lines.append(f'  "{s["keyword"]}"')
        lines.append(f'    Trang khớp nhất : {s["page"]}')
        lines.append(f'    Link từ trang   : {s["link_from"]}')
        lines.append(f'    Anchor gợi ý    : "{s["keyword"]}" (chạm {s["hits"]} token riêng)')
    lines.append("  " + "-" * 72)
    lines.append("  Link thật sự là quyết định của owner — đây chỉ là gợi ý từ dữ liệu,"
                " không tự sửa gì.")
    return "\n".join(lines)


def run_internal_links_cli() -> int:
    """`--internal-links`: in gợi ý. Không tự thêm link nào, exit 0."""
    import config.settings as cfg
    from utils.keywords import load_keywords

    target = cfg.TARGET_URL
    findings = []
    try:
        from utils.site_auditor import load_last_audit
        findings = load_last_audit()
    except Exception:
        findings = []
    history = {}
    try:
        from utils.rank_tracker import _load_history
        history = _load_history()
    except Exception:
        history = {}

    pages = collect_pages(target, audit_findings=findings,
                          rank_urls=rank_urls_from_history(history))
    keywords = load_keywords()
    suggestions = build_suggestions(keywords, pages)
    n_rank = len(pages) - len(findings) - (1 if target else 0)
    note = f"{len(pages)} trang ứng viên: {len(findings)} từ audit + {n_rank} từ rank history"
    print(suggestions_text(suggestions, source_note=note))
    return 0
