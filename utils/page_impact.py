# -*- coding: utf-8 -*-
"""utils/page_impact.py — F10e: `--page-impact` — bức tranh sức nặng theo TRANG.

Câu hỏi người quản site thật sự hỏi lúc ngồi cân ngân sách: "sức nặng của site
mình đang nằm ở trang nào?" — không phải trang nào nhiều query nhất (đã có
--gsc-pages) mà:
1. **VIP** — trang mang phần lớn imps/clicks: nếu nó rớt thì site mất bao nhiêu %?
2. **Bỏ đi tự do** — trang nào có imps mà CTR gần 0 (phơi mà không ai click →
   title/description không chạm được người tìm, hoặc sai ý tìm).
3. **Quan hệ** — mỗi trang phụ trách bao nhiêu query (n_queries) — chiều ngược
   của --gsc-pages ("trang gánh nhiều query"); ở đây là bảng đầy đủ theo trang.

Đọc lại field `pages` của snapshot GSC cuối (cùng nguồn --gsc-pages) — 0 request
mới. Chia theo TỪNG TRANG (path), mỗi query ghi trên đúng 1 trang, cộng dồn:
kết quả là bảng imps/clicks/CTR/n_queries cho từng URL. Snapshot cũ không có
`pages` → gợi ý chạy `--gsc` như --gsc-pages, không nói dối "site khỏe".

Xuất bảng console; không tự sửa gì — mọi quyết định thuộc về owner.
"""
import utils.site_paths as site_paths  # đặt chỗ banner CLI — chưa dùng thêm

VIP_IMPS_RATIO = 0.60      # một trang giữ ≥ 60% imps toàn site → đánh dấu "VIP — rớt là mất nút"
CTR_NEAR_ZERO = 0.010      # imps ≥ 100 mà CTR < 1% → hàng "phơi không ai click"
CTR_MIN_IMPS = 100         # dưới mốc imps, CTR không đáng tin → không dịnh danh
LOAD_LIMIT = 15            # bảng hiển thị tối đa N trang
QUERY_LIMIT_INLINE = 3     # mỗi trang liệt kê tối đa N query inline


def build_page_rows(pages: dict) -> list:
    """[{page, imps, clicks, ctr, n_queries, queries}] — xếp imps giảm dần,
    CTR chỉ tính khi đủ imps (dưới CTR_MIN_IMPS → None: không dịnh danh)."""
    loads: dict = {}
    for q, entries in (pages or {}).items():
        if not str(q or "").strip():
            continue
        for e in (entries or []):
            if not isinstance(e, dict) or not str(e.get("page") or "").strip():
                continue
            page = str(e["page"]).strip()
            rec = loads.setdefault(page, {"page": page, "imps": 0, "clicks": 0,
                                          "n_query": 0, "queries": set()})
            # (query, page) là 1 dòng GSC — đếm query một trang duy nhất
            if q not in rec["queries"]:
                rec["n_query"] += 1
                rec["queries"].add(q)
            rec["imps"] += int(e.get("imps") or 0)
            rec["clicks"] += int(e.get("clicks") or 0)
    rows = []
    for p in loads.values():
        imps, clicks = p["imps"], p["clicks"]
        rows.append({"page": p["page"], "imps": imps, "clicks": clicks,
                     "ctr": (clicks / imps) if imps >= CTR_MIN_IMPS else None,
                     "n_queries": p["n_query"], "queries": p["queries"]})
    rows.sort(key=lambda r: (-r["imps"], -r["clicks"], r["page"]))
    return rows


def build_impact_rows(pages: dict) -> tuple[list, dict]:
    """(rows, summary) cho cả báo cáo — summary chứa tổng + phần trăm trang đầu."""
    rows = build_page_rows(pages)
    total_imps = sum(r["imps"] for r in rows) or 1
    for r in rows:
        r["imps_share"] = r["imps"] / total_imps
    head = rows[0] if rows else None
    summary = {
        "n_pages": len(rows),
        "total_imps": sum(r["imps"] for r in rows),
        "total_clicks": sum(r["clicks"] for r in rows),
        "head_page": head["page"] if head else "",
        "head_share": head["imps_share"] if head else 0,
        "vip": bool(head and head["imps_share"] >= VIP_IMPS_RATIO and head["imps"] >= CTR_MIN_IMPS),
    }
    return rows, summary


def report_text(pages: dict, source_stamp: str = "") -> tuple[str, int]:
    """(text, số trang liệt kê). Không dữ liệu → hướng dẫn, không nền trang cong."""
    pages, stamp = _pages_from_state(pages)
    if not pages:
        return ("  Chưa có dữ liệu theo trang — chạy `python main.py --gsc`;"
                "\n  từ lần fetch sau, dữ liệu (query, page) được lưu cùng snapshot"
                "\n  (mốc cũ không được migrate — giống --gsc-pages)."), 0
    rows, summary = build_impact_rows(pages)
    if not rows:
        return (f"  Snapshot {stamp} không có imps nào theo trang — "
                "chưa nói được sức nặng."), 0

    lines = [f"  SỨC NẶNG THEO TRANG (snapshot {stamp})",
             "  " + "-" * 70]
    tr_imps, tr_clicks = summary["total_imps"], summary["total_clicks"]
    site_ctr = tr_clicks / tr_imps if tr_imps >= CTR_MIN_IMPS else None
    lines.append(f"  Toàn site: {tr_imps} imps, {tr_clicks} clicks"
                 + (f", CTR {site_ctr:.1%}" if site_ctr is not None else ""))
    if summary["vip"]:
        lines.append("  ⚠️ Trang đứng đầu gánh "
                     f"{summary['head_share']:.0%} imps — site PHỤ THUỘC 1 trang VIP,"
                     " rớt là mất nền imps. Cần site đa nền.")
    lines.append("  " + "-" * 70)
    lines.append(f"  {'Trang':<44}{'Imps':>7}{'Clicks':>7}{'CTR':>7}{'%':>7}{'Qry':>4}")
    for r in rows[:LOAD_LIMIT]:
        ctr = f"{r['ctr']:.1%}" if isinstance(r["ctr"], float) and r["ctr"] is not None else "-"
        share = summary["head_share"] if r is rows[0] else r["imps_share"]
        share_txt = f"{share:.0%}"
        flag = " 👑" if (r is rows[0] and summary["vip"]) else ""
        lines.append(f'  {r["page"][:44]:<44}{r["imps"]:>7}{r["clicks"]:>7}'
                     f'{ctr:>7}{share_txt:>7}{r["n_queries"]:>4}{flag}')

    # hàng "phơi không ai click" — imps đủ mà CTR gần 0
    floppy = [r for r in rows
              if isinstance(r["ctr"], float) and r["ctr"] is not None
              and r["ctr"] < CTR_NEAR_ZERO and r["imps"] > 0]
    if floppy:
        lines.append("")
        lines.append(f"  PHƠI MÀ KHÔNG AI CLICK ({len(floppy)} trang, "
                     f"CTR < {CTR_NEAR_ZERO:.0%} và imps ≥ {CTR_MIN_IMPS}):")
        for r in floppy[:5]:
            lines.append(f'  · {r["page"][:60]}  ({r["imps"]} imps, CTR {r["ctr"]:.1%}'
                         " — title/description chưa chạm được người tìm)")
    lines.append("")
    lines.append("  Chia ngân sách theo bảng trên — quyết định của owner, tool chỉ xếp hạng.")
    return "\n".join(lines), min(len(rows), LOAD_LIMIT)


def _pages_from_state(pages: dict = None) -> tuple[dict, str]:
    """(pages snapshot cuối, ngày) — cho phép test truyền pages thẳng vào."""
    if pages is not None:
        return pages, "(dữ liệu truyền vào)"
    from utils.gsc_pages import _snapshot_pages
    return _snapshot_pages()


def run_page_impact_cli() -> int:
    """`--page-impact`: bức tranh sức nặng theo trang từ snapshot GSC cuối."""
    import config.settings as cfg

    pages, stamp = _pages_from_state()
    if not pages:
        text, _ = report_text(None)
    else:
        text, _ = report_text(pages, source_stamp=stamp)
    print("=" * 104)
    print(f"  SỨC NẶNG THEO TRANG — {getattr(cfg, 'TARGET_URL', '') or '(chưa cấu hình site)'}")
    print("=" * 76)
    print(text)
    print("=" * 104)
    return 0