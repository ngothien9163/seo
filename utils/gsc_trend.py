# -*- coding: utf-8 -*-
"""utils/gsc_trend.py — G-B2: xu hướng theo query từ lịch sử GSC.

Đọc gsc_history.json (90 mốc tối đa), 0 request mới:
- mỗi query (kể cả query mới không nằm trong danh sách từ khóa) hiển thị
  impressions / clicks / CTR / vị trí trung bình của 8 snapshot gần nhất
  (collect SS mỗi mốc từ GSC API kèm snapshot ngày);
- thay đổi giữa lần fetch gần nhất vs trước trỏ chủ thể đáng mắt — query nào
  sụt impressions mạnh là tín hiệu sớm trước khi hạng rớt (với site tụt khỏi
  top 100, đây là cách đo còn lại).

Chỉ READ — không ghi file, không đụng rate limit (fetch đã xong trước đó).
"""
from utils.gsc_client import _load_history, _fold
from utils.rank_tracker import sparkline
# sparkline sinh cho HẠNG (số nhỏ = tốt); trend imps thì số lớn = tốt
# nên report_text đảo trước khi vẽ.

TREND_WIDTH = 8        # mốc hiển thị trong sparkline
TREND_DROP_IMPS = 0.5  # (tỷ lệ) imps mốc mới < 50% mốc trước → cờ ⬇️ (sụt đáng kể)


def query_series(history: dict, query: str, field: str, width: int = TREND_WIDTH) -> list:
    """[giá trị field] 8 snapshot gần nhất của query (thiếu → None)."""
    snaps = history.get("snapshots") or {}
    out = []
    for stamp in sorted(snaps.keys())[-width:]:
        row = ((snaps[stamp].get("rows") or {}).get(query) or {})
        v = row.get(field)
        out.append(int(v) if field in ("clicks", "impressions") and v is not None
                   else (float(v) if v is not None else None))
    return out


def _is_tracked(query: str, tracked_set: frozenset) -> bool:
    """query trùng (sau khi fold) một từ khóa đang theo dõi — dùng _fold chung
    của gsc_client: "noi mi quan 2" và "Nối Mi Quận 2" là một."""
    qf = _fold(query)
    return any(_fold(t) == qf for t in tracked_set) if qf else False


def build_rows(history: dict, tracked: list = None) -> list[dict]:
    """{query, tracked, clicks/imps/ctr/pos, dropped, n_snapshots} theo mốc 8
    snapshot gần nhất. Series CANH theo mốc: query vắng ở mốc nào → imps/clicks
    0 mốc đó (nó thuộc cơ/theo đúng nghĩa — Google ngừng phơi, không phải
    "không có dữ liệu"); ctr/pos = None (không đo được, sparkline vẽ '·').
    """
    tracked_set = set(tracked or [])
    snaps = history.get("snapshots") or {}
    if not snaps:
        return []
    stamps = sorted(snaps.keys())[-TREND_WIDTH:]

    rows_out = {}
    for stamp in stamps:
        for q in set(rows_out) | set((snaps[stamp].get("rows") or {})):
            rec = rows_out.setdefault(q, {
                "query": q,
                "tracked": _is_tracked(q, tracked_set),
                "clicks": [], "imps": [], "ctr": [], "pos": [],
            })
            r = ((snaps[stamp].get("rows") or {}).get(q) or {})
            rec["clicks"].append(int(r.get("clicks") or 0))
            rec["imps"].append(int(r.get("impressions") or 0))
            rec["ctr"].append(float(r["ctr"]) * 100 if r.get("ctr") is not None else None)
            rec["pos"].append(float(r["position"]) if r.get("position") is not None else None)

    out = []
    for q, rec in rows_out.items():
        imps_last = rec["imps"][-1]
        imps_prev = rec["imps"][-2] if len(rec["imps"]) >= 2 else None
        dropped = (imps_prev is not None and imps_prev > 0
                   and imps_last / imps_prev < TREND_DROP_IMPS)
        out.append({"query": q, "tracked": rec["tracked"],
                    "clicks": rec["clicks"], "imps": rec["imps"],
                    "ctr": rec["ctr"], "pos": rec["pos"], "dropped": dropped,
                    "n_snapshots": len(rec["imps"])})
    out.sort(key=lambda r: (-r["imps"][-1] if r["imps"] else 0, r["query"]))
    return out


def _fmt(vals: list, fmt: str) -> str:
    known = [v for v in vals if v is not None]
    return (fmt.format(known[-1]) if known else "—")


def report_text(history: dict, tracked: list = None) -> tuple[str, int]:
    """(text, số query đang hiển thị). Không có mốc → hướng dẫn chạy --gsc."""
    rows = build_rows(history, tracked)
    if not rows:
        return ("  Chưa có mốc Search Console nào — chạy `python main.py --gsc`;"
                "\n  từ mốc thứ hai, xu hướng theo query được tính. Cần ≥ 2 mốc"
                "\n  để thấy 'lên/đuổi' — chưa fetch lần nào thì chưa có gì để so."), 0

    lines = [f"  XU HƯỚNG THEO QUERY ({len(rows)} query, 8 mốc GSC gần nhất)",
             "  " + "-" * 100,
             f"  {'Query':<34}{'Tracked':>7}{'Clicks':>7}{'Imps':>6}"
             f"{'CTR':>7}{'Pos':>6}  {'Xu hướng imps':<8}{'⚠️ Sụt':>6}"]
    for r in rows[:20]:
        click_s = str(r["clicks"][-1])
        imps_s = str(r["imps"][-1])
        pos = _fmt(r["pos"], "{:.1f}")
        ctr = _fmt(r["ctr"], "{:.1f}%")
        spark = sparkline(r["imps"], TREND_WIDTH)
        flag = "  ⬇️" if r["dropped"] else ""
        track = "✓" if r["tracked"] else ""
        lines.append(f'  {r["query"][:34]:<34}{track:>7}{click_s:>7}{imps_s:>6}'
                     f'{ctr:>7}{pos:>6}  {spark:<8}{flag}')
    lines.append("  " + "-" * 100)
    lines.append("  Xu hướng vẽ IMPS của từng mốc fetch — cột càng cao impressions càng"
                 " nhiều (thứ tự fetch, không phải theo ngày).")
    lines.append("  ⬇️ = imps mốc mới < 50% mốc trước (tín hiệu sớm — hạng SERP có thể chưa rớt).")
    lines.append("  Query SỤT mạnh về imps mà chưa rớt hạng thường là dấu hiệu Google giảm"
                 " phơi trang cho query đó.")
    return "\n".join(lines), min(len(rows), 20)


def run_gsc_trend_cli() -> int:
    """`--gsc-trend`: xu hướng imps/clicks/CTR/pos theo query 8 mốc."""
    import config.settings as cfg
    from utils.keywords import load_keywords

    tracked = load_keywords()
    history = _load_history()
    text, n = report_text(history, tracked)
    print("=" * 104)
    print(f"  GSC TREND — {getattr(cfg, 'TARGET_URL', '') or '(chưa cấu hình site)'}")
    print("=" * 104)
    print(text)
    print("=" * 104)
    return 0
