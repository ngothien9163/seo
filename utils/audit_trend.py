# -*- coding: utf-8 -*-
"""
utils/audit_trend.py — T41: audit trend theo THỜI GIAN — mỗi rule đếm qua
tất cả mốc trong audit_history.json (tối đa 20 mốc, tự append mỗi lần --audit).

Khác --audit-diff (G-3): diff chỉ so 2 mốc gần nhất theo lỗi đơn lẻ (url cụ
thể đã sửa/chưa); trend này trả lời "quá trình sửa nội bộ có tác dụng không"
— alt 34 → 28 → 12 là tiến bộ thật, đếm lỗi đơn lẻ không nói được.

Dữ liệu từ audit_history.json có sẵn từ trước (0 request mới, không đổi format
file — đếm trực tiếp findings trong mỗi mốc). Mốc thiếu findings bị bỏ qua.
"""
from utils.site_auditor import load_audit_history

TOP_RULES = 8          # bảng trend hiển thị tối đa bao nhiêu rule


def rule_counts_through_time(history: list) -> list:
    """[{'rule', 'series': [counts cũ→mới], 'first_count', 'last', 'peak',
    'delta', 'prev'}] — hoặc [] khi thiếu (0/1 mốc).
    Series đủ dài = số mốc: rule mới xuất hiện giữa chuỗi có cửa 0 cho các
    mốc trước khi nó ra đời (không gán "lỗi" cho lần audit chưa có nó).
    Thứ tự: giảm last_count rồi tên."""
    records = [m for m in (history or [])
               if isinstance(m, dict) and isinstance(m.get("findings"), list)]
    if len(records) < 2:
        return []
    per_milestone = []
    for rec in records:
        by_rule = {}
        for f in rec["findings"]:
            if isinstance(f, dict) and f.get("rule"):
                by_rule[f["rule"]] = by_rule.get(f["rule"], 0) + 1
        per_milestone.append(by_rule)
    all_rules = sorted({rule for by_rule in per_milestone for rule in by_rule})
    out = []
    for rule in all_rules:
        series = [by_rule.get(rule, 0) for by_rule in per_milestone]
        last = series[-1]
        out.append({"rule": rule, "series": series,
                    "first_count": series[0], "last": last, "peak": max(series),
                    "delta": last - series[0],
                    "prev": series[-2] if len(series) >= 2 else None})
    out.sort(key=lambda d: (-d["last"], d["rule"]))
    return out


def _arrow(delta_pair) -> str:
    """(prev, cur) → '↓' tiến bộ / '↑' xấu đi / '—' đứng yên. Giảm = tốt."""
    if not delta_pair or None in delta_pair:
        return "—"
    prev, cur = delta_pair
    if cur < prev:
        return "↓"
    if cur > prev:
        return "↑"
    return "—"


def trend_text(history: list = None, keep: int = 10) -> str:
    """Bảng text cho --audit-trend: rule | mốc đầu → hiện tại (peak) mũi tên.
    Thiếu dữ liệu → hướng dẫn, không nói dối."""
    if history is None:
        history = load_audit_history()
    rows = rule_counts_through_time(history)
    if not rows:
        n = len([m for m in (history or []) if isinstance(m, dict)])
        if len(history or []) <= 1:
            return ("  Lịch sử audit mới có 0–1 mốc — chưa vẽ được trend."
                    "\n  Chạy `python main.py --audit` thêm (mỗi lần 1 mốc,"
                    "\n  tối đa 20 mốc gần nhất được so).")
        return "  Lịch sử audit hỏng shape (findings thiếu) — chạy lại --audit."
    records = [m for m in history if isinstance(m, dict) and isinstance(m.get("findings"), list)]
    lines = ["  AUDIT TREND — từng loại lỗi qua các lần audit",
             f"   mốc: {len(records)} (từ {records[0].get('saved_at', '?')[:16]}"
             f" đến {records[-1].get('saved_at', '?')[:16]})",
             "   ↓ = giảm tốt │ ↑ = tăng │ — = đứng yên",
             "  " + "-" * 68]
    total_first = sum(r["first_count"] for r in rows)
    total_last = sum(r["last"] for r in rows)
    mark = "↓" if total_last < total_first else "↑" if total_last > total_first else "—"
    lines.append(f"  TỔNG LỖI: {total_first} → {total_last} {mark} "
                 f"({total_last - total_first:+d} so mốc đầu trong {len(records)} lần)")
    lines.append("")
    for r in rows[:keep]:
        series_show = " ".join(str(n) for n in r["series"][-8:])
        arrow = _arrow((r["prev"], r["last"]))
        delta_txt = "" if r["delta"] == 0 else f' ({r["delta"]:+d})'
        lines.append(f'  {r["rule"]:<28} {series_show:<24} {arrow}{delta_txt}')
    if len(rows) > keep:
        lines.append(f"  … và {len(rows) - keep} rule nữa (count thấp hơn).")
    lines.append("")
    lines.append("  Đủ bảng HTML có màu: python main.py --html-report (section Audit).")
    return "\n".join(lines)


def trend_summary_for_html(history: list = None) -> dict:
    """Dữ liệu cho section Audit trong report.html: {n_checks, span, rules:
    [{rule, first, last, peak, series(cuối 8), delta, arrow}] tối đa 8}
    + trend tổng. Không đủ 2 mốc → {} (section giữ gì cũ, không nói dối)."""
    if history is None:
        history = load_audit_history()
    rows = rule_counts_through_time(history) if history else []
    if not rows:
        return {}
    total_first = sum(r["first_count"] for r in rows)
    total_last = sum(r["last"] for r in rows)
    return {"n_checks": len([m for m in history
                             if isinstance(m, dict) and isinstance(m.get("findings"), list)]),
            "total_first": total_first, "total_last": total_last,
            "rules": [{"rule": r["rule"], "first": r["first_count"], "last": r["last"],
                       "peak": r["peak"], "series": r["series"][-8:], "delta": r["delta"],
                       "arrow": _arrow((r["prev"], r["last"]))} for r in rows[:8]],
            "n_rules_all": len(rows)}


def run_audit_trend_cli() -> int:
    """Entry `--audit-trend` — in bảng trend, không gọi mạng."""
    print(trend_text())
    return 0
