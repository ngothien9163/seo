# -*- coding: utf-8 -*-
"""utils/competitors.py — P2-1: domain nào thường giành SERP theo từ khóa?

Đọc rank history đã lưu `top_urls` (10 URL organic đầu mỗi từ khóa, thêm lúc
check rank — không tốn thêm request nào). Đếm tần suất domain:
- toàn lịch sử → bảng domain tổng
- theo từng từ khóa → domain nào cạnh trực tiếp ở từ khóa đó

Đếm tuần suất XUẤT HIỆN trên top-10, không khẳng định ai 'chiếm hạng' — SERP
luôn biến động, đây chỉ để nhận diện đối thủ thường trực.
"""
from collections import Counter
from urllib.parse import urlparse

_SKIP_NETLOC = ("google.", "googleusercontent.", "gstatic.", "googleadservices.",
                "doubleclick.", "youtube.", "facebook.", "bing.")


def _domain(url: str) -> str:
    try:
        host = (urlparse(url).netloc or "").lower()
    except ValueError:
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host


def _organic(domain: str) -> bool:
    """Domain (đã trích sẵn) có phải kết quả organic — loại Google/YT/ads."""
    d = str(domain or "").lower()
    return bool(d) and not any(d.startswith(s) for s in _SKIP_NETLOC)


def _competitor_domains(urls: list) -> list[str]:
    """URL list → domain organic (sắp xếp hợp lý: giữ nguyên thứ tự xuất hiện)."""
    out, seen = [], set()
    for u in urls or []:
        d = _domain(u)
        if not d or d in seen or not _organic(d):
            continue
        seen.add(d)
        out.append(d)
    return out


def competitor_history_from(history: dict, own_domain: str = ""):  # noqa: C901
    """Rank history → (per_kw: {kw: Counter}, own_domain, stamps_covered).

    Chỉ đọc các mốc từng lưu top_urls; mốc cũ (trước khi có P2) tự bỏ qua —
    không phải migrate lại file history.
    """
    per_kw: dict = {}
    stamps_covered = set()
    for stamp, entry in (history.get("checks") or {}).items():
        for kw, val in (entry or {}).items():
            top = ((val or {}).get("top_urls") or []) if isinstance(val, dict) else []
            doms = _competitor_domains(top)
            if not doms:
                continue
            stamps_covered.add(stamp)
            c = per_kw.setdefault(kw, Counter())
            for d in doms:
                c[d] += 1
    return per_kw, own_domain, stamps_covered


def overall_top(per_kw: dict, own_domain: str = "", limit: int = 10) -> list[tuple]:
    """(domain, lần xuất hiện) toàn bộ từ khóa, loại chính site mình."""
    c = Counter()
    for kw, per in per_kw.items():
        for d, n in per.items():
            if d and d != own_domain:
                c[d] += n
    return c.most_common(int(limit))


def per_keyword_top(per_kw: dict, keyword: str, own_domain: str = "",
                    limit: int = 5) -> list[tuple]:
    return [(d, n) for d, n in (per_kw.get(keyword) or Counter()).most_common(int(limit))
            if d and d != own_domain]


def format_overall(rows, stamps: int, kws: int) -> str:
    lines = [f"  DOMAIN ĐỐI THỦ xuất hiện nhiều nhất ({kws} từ khóa × {stamps} mốc có dữ liệu SERP)",
             "  " + "-" * 60]
    if not rows:
        lines.append("  Chưa đủ dữ liệu — lịch sử rank có 'top_urls' từ lần check tới đây.")
        lines.append("  Chạy python main.py --rank (≥ 2 lần cho tần suất có ý nghĩa).")
        return "\n".join(lines)
    lines.append(f"  {'Domain':<35}{'Xuất hiện':>10}")
    lines.append("  " + "-" * 60)
    for d, n in rows:
        lines.append(f"  {d:<35}{n:>10}")
    return "\n".join(lines)


def format_keyword(per_kw: dict, keyword: str, own_domain: str = "") -> str:
    rows = per_keyword_top(per_kw, keyword, own_domain)
    lines = [f'  "{keyword}":']
    if not rows:
        lines.append("    chưa có competitor được lưu — mốc này chưa có dữ liệu hoặc "
                     "từ khóa chưa từng có top_urls.")
        return "\n".join(lines)
    top = ", ".join(f"{d} ({n})" for d, n in rows)
    lines.append(f"    {top}")
    return "\n".join(lines)


def run_competitors_cli() -> int:
    """`--competitors`: bảng domain + theo từ khóa. Đọc history, không mạng."""
    import config.settings as cfg
    from utils.rank_tracker import _load_history

    history = _load_history()
    own = _domain_from_target(cfg.TARGET_URL)
    per_kw, _, stamps = competitor_history_from(history, own)
    keywords_with_data = len([1 for per in per_kw.values() if per])
    print(format_overall(overall_top(per_kw, own), len(stamps), keywords_with_data))
    print()
    for kw in sorted(per_kw):
        print(format_keyword(per_kw, kw, own))
    return 0


def _domain_from_target(target: str) -> str:
    try:
        host = (urlparse(target).netloc or "").lower()
    except ValueError:
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host
