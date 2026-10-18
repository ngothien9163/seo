# -*- coding: utf-8 -*-
"""utils/gsc_pages.py — bộ G tiếp theo: cannibalization theo dữ liệu Google thật.

Đọc field `pages` của snapshot GSC cuối (lưu từ lần fetch có tính năng;
các mốc cũ không có field → mục này tự nói ghich rõ, không migrate):

- **Cannibalization**: query được N trang cùng site chia sẻ (dimension
  ["query","page"] từ GSC — Google nói chính nó hiển thị trang nào, không
  đoán từ top_urls như --rank-urls).
- **Trang gánh nhiều query nhất**: phía ngược — trang nào đang phục
  N query (ảnh vật đeo của site).

0 request mới, chỉ READ gsc_history.json — thuần tính.
"""
from utils.gsc_client import _load_history

import config.settings as cfg
import utils.site_paths as _sp

_GSC_NAME = "gsc_history.json"

CANNIB_MIN_IMPS = 30      # imps tổng của query — dưới mốc là nhiễu, không cảnh báo
CANNIB_MIN_PAGES = 2      # trang tối thiểu để là "nhiều trang cùng đấm"
PAGE_LOAD_LIMIT = 15      # "trang gánh nhiều query" hiển thị tối đa
PAGE_MIN_QUERIES = 2      # trang gánh dưới mốc này không đáng liệt kê

def _snapshot_pages() -> tuple[dict, str]:
    """(pages của snapshot cuối, key ngày) hoặc ({}, '')."""
    snaps = _load_history().get("snapshots") or {}
    if not snaps:
        return {}, ""
    last = sorted(snaps.keys())[-1]
    pages = snaps[last].get("pages") or {}
    return (pages if isinstance(pages, dict) else {}), last


def _norm_url(url: str) -> str:
    """URL GSC (đủ full https://host/path) → path + query ngắn, hiển thị bảng."""
    from urllib.parse import urlsplit
    p = urlsplit(str(url or ""))
    out = (p.path or "/").rstrip("/")
    if p.query:
        out += "?" + p.query[:12] + ("…" if len(p.query) > 12 else "")
    # host lạ (KHÔNG phải site mình) — giữ lại để khỏi nhầm trang của site khác
    site_host = urlsplit(str(getattr(cfg, "TARGET_URL", "") or "")).netloc.lower()
    own = not p.netloc or not site_host or p.netloc.lower().lstrip("www.") == site_host.lstrip("www.")
    if not own:
        out = f"{p.netloc}{out}"
    return out or "/"


def build_cannibals(pages: dict) -> list[dict]:
    """{query, imps, clicks, n_pages, pages}: query đủ imps mà ≥ 2 trang của
    site chia sẻ (imps từng trang đều ngưỡng? — TỔNG đủ là đủ: trang ít imps
    là dấu hiệu Google đang thử, cùng họi cần hợp nhất)."""
    out = []
    for q, entries in (pages or {}).items():
        entries = [e for e in (entries or []) if isinstance(e, dict)]
        total_imps = sum(int(e.get("imps") or 0) for e in entries)
        total_clicks = sum(int(e.get("clicks") or 0) for e in entries)
        real = [e for e in entries if int(e.get("imps") or 0) > 0 or int(e.get("clicks") or 0) > 0]
        if total_imps < CANNIB_MIN_IMPS or len(real) < CANNIB_MIN_PAGES:
            continue
        out.append({"query": str(q), "imps": total_imps, "clicks": total_clicks,
                    "n_pages": len(real), "pages": sorted(
                        (str(e.get("page") or "") for e in real))})
    out.sort(key=lambda r: (-r["imps"], r["query"]))
    return out


def build_page_loads(pages: dict) -> list[dict]:
    """{page, queries, imps, clicks} — trang nào gánh N query (ƙ приб N ≥ PAGE_MIN_QUERIES)."""
    loads: dict = {}
    for q, entries in (pages or {}).items():
        entries = [e for e in (entries or []) if isinstance(e, dict)]
        # hình dáng cùng query trông 2 mốc: query + một trang = một phần việc
        for e in entries:
            page = str(e.get("page") or "")
            if not page:
                continue
            rec = loads.setdefault(page, {"page": page, "queries": set(),
                                          "imps": 0, "clicks": 0})
            # một query trên một trang chỉ tính DUY NHẤT (GSC có thể trả 2 hàng?)
            if q not in rec["queries"]:
                rec["queries"].add(q)
            rec["imps"] += int(e.get("imps") or 0)
            rec["clicks"] += int(e.get("clicks") or 0)
    out = [{"page": p["page"], "n_queries": len(p["queries"]),
            "queries": sorted(p["queries"]),
            "imps": p["imps"], "clicks": p["clicks"]}
           for p in loads.values() if len(p["queries"]) >= PAGE_MIN_QUERIES]
    out.sort(key=lambda r: (-r["n_queries"], -r["imps"], r["page"]))
    return out[:PAGE_LOAD_LIMIT]


def build_report_text() -> tuple[str, int]:
    """(text, số query cannibal). Không `pages` → gợi ý lệnh, không nói dối."""
    pages, stamp = _snapshot_pages()
    if not pages:
        return ("  Chưa có dữ liệu theo trang — chạy `python main.py --gsc`;"
                "\n  từ lần fetch sau khi có tính năng, dữ liệu (query, page)"
                "\n  được lưu cùng snapshot (mốc cũ không được migrate)."), 0

    cannibals = build_cannibals(pages)
    page_loads = build_page_loads(pages)
    stamp_note = f" (snapshot {stamp})"
    if not cannibals and not page_loads:
        return (f"  Không có dấu hiệu cannibalization hay chồng query{stamp_note}.\n"
                f"  Mỗi query do 1 trang phụ trách, hoặc không đủ imps để nói"
                f" (ngưỡng {CANNIB_MIN_IMPS})."), 0

    lines = [f"  CANNIBALIZATION THEO GOOGLE THẬT{stamp_note}",
             "  " + "-" * 68]
    if cannibals:
        lines.append(f"  NHIỀU TRANG CÙNG PHỤC VỤ ({len(cannibals)} query):")
        lines.append(f"  {'Query':<34}{'Trang':>5}{'Imps':>7}{'Clicks':>7}")
        for r in cannibals[:15]:
            lines.append(f'  {r["query"][:34]:<34}{r["n_pages"]:>5}'
                         f'{r["imps"]:>7}{r["clicks"]:>7}')
            shown = [_norm_url(p) for p in r["pages"][:3]]
            lines.append(f'  {"":>46}{"; ".join(shown)}')
            if len(r["pages"]) > 3:
                lines.append(f'  {"":>46}… và {len(r["pages"]) - 3} trang nữa')
        lines.append("  Google chưa chốt trang 'chính' cho query — dùng --internal-links để")
        lines.append("  chốt link nội bộ về một trang, hoặc hợp nhất/301 (nội dung trùng).")
    else:
        lines.append(f"  Không query nào chịu ≥ {CANNIB_MIN_PAGES} trang cùng site"
                     f" (ngưỡng {CANNIB_MIN_IMPS} imps).")
        lines.append("  Google đang chốt trang khá sạch cho từng query.")

    if page_loads:
        lines.append("")
        lines.append(f"  TRANG GÁNH NHIỀU QUERY NHẤT (tính cả query không phải từ khóa theo dõi):")
        for r in page_loads[:10]:
            lines.append(f'  {_norm_url(r["page"]):<46}{r["n_queries"]:>3} query  '
                         f'{r["imps"]:>6} imps{r["clicks"]:>7} clicks')
    return "\n".join(lines), len(cannibals)


def run_gsc_pages_cli() -> int:
    """`--gsc-pages`: cannibalization từ dữ liệu (query, page) của Google thật."""
    text, n = build_report_text()
    print("=" * 76)
    print(f"  GSC THEO TRANG — {getattr(cfg, 'TARGET_URL', '') or '(chưa cấu hình site)'}")
    print("=" * 76)
    print(text)
    print("=" * 76)
    return 0
