# -*- coding: utf-8 -*-
"""utils/content_gap.py — F10f: `--content-gap` — Google muốn, site CHƯA có.

Ngược của --page-impact (trang có đủ sức nặng chưa?): lệnh này hỏi "Google
đang phơi những Query nào mà site mình CHƯA có trang đúng nghĩa cho query đó".

Nguồn (0 request mới):
- **Field `pages` snapshot GSC cuối** (cùng nguồn --gsc-pages/--page-impact):
  tên đúng Google chỉ định trang nào trả lời query — nếu trang đó chỉ là
  trang chủ "/" nghĩa là site chưa có bài riêng cho query, Google phải mượn
  trang chủ trả lời.

Ngưỡng imps (GAP_MIN_IMPS, mặc định 10) tránh dỏm: Google "thử" vài imps cho
mọi query. Chỉ READ — không sinh bài, không đụng content plan; gợi ý
`--generate --day N` chỉ là nhắc việc cho owner.

Cả hai nguồn, cùng quy tắc: query đủ imps mà URL phụ trách là TRANG CHỦ
→ site chưa có bài riêng, Google phải "mượn" trang chủ trả lời.
"""
GAP_MIN_IMPS = 10          # imps đủ để Google "muốn thật" (10+ cho query demo nhỏ)
GAP_LIST_LIMIT = 15        # bảng hiển thị tối đa N query

def _foldify(s: str) -> str:
    """Fold không dấu — gọi gsc_client._fold (bản duy nhất của repo)."""
    from utils.gsc_client import _fold
    return _fold(s)

def _query_tokens(q: str) -> list:
    """Token có nghĩa của query (fold không dấu) — dùng khi lọc gap theo từ khóa."""
    from utils.audit_actions import _kw_tokens
    return _kw_tokens(q)

def build_gaps(pages: dict) -> list:
    """[gap] từ pages GSC: query đủ imps mà trang phụ trách là trang chủ.

    Quy tắc đơn giản và đúng nguồn: Google TỰ chỉ định từng trang trả lời
    query nào — trang chủ gánh nhiều query quan trọng là dấu hiệu 'chưa có
    bài riêng'. (rank history không đủ chốt vì URL rank có khi là trang chủ
    đúng legitimately — dùng nguồn GSC làm chuẩn thôi.)"""

    out = []
    seen = set()
    from urllib.parse import urlsplit

    def is_home(url: str) -> bool:
        path = urlsplit(str(url or "")).path or "/"
        return path in ("/", "") or path.rstrip("/") == ""

    for q, entries in (pages or {}).items():
        if not str(q or "").strip():
            continue
        entries = [e for e in (entries or []) if isinstance(e, dict)]
        if not entries:
            continue
        top = max(entries, key=lambda e: (int(e.get("imps") or 0), int(e.get("clicks") or 0)))
        imps = int(top.get("imps") or 0)
        page = str(top.get("page") or "")
        if imps < GAP_MIN_IMPS or not is_home(page):
            continue
        key = _foldify(str(q))
        if key in seen:
            continue
        seen.add(key)
        out.append({"query": str(q), "imps": imps,
                    "clicks": int(top.get("clicks") or 0), "page": page})
    out.sort(key=lambda r: (-r["imps"], r["query"]))
    return out[:GAP_LIST_LIMIT]


def gap_text(rows: list) -> str:
    """Bảng tính đơn giản — giữ nguyên tên query dấu (không fold tên)."""
    if not rows:
        return ("  Không query nào bị tình trạng trên, hoặc chưa đủ imps "
                "(ngưỡng 10).")
    lines = [f"  GOOGLE MUỐN, SITE CHƯA CÓ TRANG ({len(rows)} query):",
             "  " + "-" * 70,
             f"  {'Query':<40}{'Imps':>7}{'Clicks':>7}{'Đang trả lời':>12}"]
    for r in rows:
        lines.append(f'  {r["query"][:40]:<40}{r["imps"]:>7}{r["clicks"]:>7}'
                     f'{"trang chủ":>12}')
    lines.append("  " + "-" * 70)
    lines.append("  Bài mới cho từng query: chọn hướng —")
    lines.append("  `--generate --day N` (plan 30 ngày) hoặc tự viết draft rồi `--wp-push`.")
    return "\n".join(lines)


def run_content_gap_cli() -> int:
    """`--content-gap`: query Google đang phơi mà site chưa có trang riêng."""
    import config.settings as cfg
    from utils.gsc_pages import _snapshot_pages

    pages, stamp = _snapshot_pages()
    if not pages:
        print("=" * 104)
        print(f"  CONTENT GAP — {getattr(cfg, 'TARGET_URL', '') or '(chưa cấu hình site)'}")
        print("=" * 76)
        print("  Chưa có dữ liệu theo trang — chạy `python main.py --gsc`;")
        print("  từ lần fetch sau, dữ liệu (query, page) được lưu cùng snapshot.")
        print("=" * 104)
        return 0

    gaps = build_gaps(pages)
    print("=" * 104)
    print(f"  CONTENT GAP — {getattr(cfg, 'TARGET_URL', '') or '(chưa cấu hình site)'}"
          f"  (snapshot {stamp})")
    print("=" * 76)
    print(gap_text(gaps))
    print("=" * 104)
    return 0
