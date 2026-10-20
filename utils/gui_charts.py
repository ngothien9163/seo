# -*- coding: utf-8 -*-
"""utils/gui_charts.py — F10k: chart vẽ trong GUI bằng tkinter canvas (0 dependency mới).

Nút GSC TREND hiện tại chỉ in sparkline ASCII vào log. Nút mới **📈 CHART**
vẽ đường thật (line + điểm + nhãn) vào một CTkCanvas trong tab Xếp Hạng — hạng
số nhỏ = tốt nên đường đi LÊN nghĩa là TỐT (đảo trục: y = hạng 1 ở trên).

Thiết kế:
- `chart_items(points, w, h)` là hàm THUẦN trả list lệnh canvas
  ("line", pts) / ("oval", x, y, r) / ("text", x, y, s) — test khẳng hình
  đúng mà không cần GUI; GUI chỉ dịch lệnh thành create_*.
- Worker đọc rank history trong thread (kw đang theo dõi, 8 mốc gần nhất,
  ưu tiên kw có hạng), rồi `self.after(0, ...)` vẽ vào canvas.
- Không dependency mới; canvas hỏng (không Ttk) thì chỉ in báo lỗi, không crash.

T31 thêm AEO trend: `aeo_trend_series(history)` → {"labels": [tuần], "series":
{"AI nhắc (tổng)": [%], engine: [%]}} — đường % (0-100, cao = tốt — KHÔNG đảo
trục); worker gọi y như CHART nhưng canvas nằm ở tab 📢 AI Nói Gì.
"""
import re
from collections import Counter
from datetime import date as _date

CHART_WIDTH = 8          # dùng 8 mốc gần nhất, khớp TREND_WIDTH của gsc-trend
CHART_MARGIN = 28        # lề cho nhãn
TOP_KEYWORDS = 5         # nhiều hơn là rối — vẽ tối đa 5 đường

PALETTE = ("#4fc3f7", "#81c784", "#ffb74d", "#e57373", "#ba68c8")
INK = "#cfcfd8"
GRID = "#3a3a44"


def chart_items(series: dict, w: int, h: int, invert_y: bool = True,
                x_labels: list | None = None) -> list:
    """THUẦN: {label: [giá trị mốc]} → item canvas.

    invert_y=True (rank): giá trị NHỎ ở TRÊN (hạng 1 = đỉnh). Giá trị None là lỗ — đường đứt tại đó (nối từng đoạn liên tục).
    x_labels (T31): nhãn trục x từng cột (tuần ISO của AEO trend) → item
    ("xlab", x, y, text, "center"); None = không có (chart hạng cũ).
    Item hình: ("line", color, [đoạn]) với đoạn = (i, x1, y1, x2, y2),
    ("dot", color, x, y), ("label", x, y, text, anchor).
    """
    if not series or w <= 2 * CHART_MARGIN or h <= 2 * CHART_MARGIN:
        return []
    labels = list(series.keys())[:TOP_KEYWORDS]
    vals_all = [v for lab in labels for v in (series[lab] or [])
                if isinstance(v, (int, float))]
    if not vals_all:
        return []
    lo = min(vals_all)
    hi = max(vals_all)
    if hi == lo:
        hi = lo + 1
    n_x = max(max(len(series[lab] or []) for lab in labels), 2) - 1
    x_left, x_right = CHART_MARGIN, w - CHART_MARGIN
    y_top, y_bottom = CHART_MARGIN, h - CHART_MARGIN

    def to_xy(v, i):
        x = x_left + (x_right - x_left) * (i / n_x)
        frac = ((v - lo) / (hi - lo))
        if invert_y:
            y = y_top + (y_bottom - y_top) * frac   # giá trị NHỎ ở TRÊN (hạng 1 = đỉnh)
        else:
            y = y_bottom - (y_bottom - y_top) * frac  # trục toán học: CAO ở trên (AEO %)
        return x, y

    items = []
    # lưới ngang: min / giữa / max
    for gv, gy in ((lo, y_top if invert_y else y_bottom),
                   ((lo + hi) / 2, (y_top + y_bottom) / 2),
                   (hi, y_bottom if invert_y else y_top)):
        items.append(("grid", gy, f"{gv:g}"))
    # nhãn trục x (T31) — hàng dưới cùng, mỗi cột một nhãn
    if x_labels:
        n_lbl = max(len(x_labels), 2) - 1
        for i, txt in enumerate(x_labels[:n_lbl + 1]):
            x = x_left + (x_right - x_left) * (i / n_lbl)
            items.append(("xlab", x, y_bottom + 14, str(txt), "center"))
    for k, lab in enumerate(labels):
        color = PALETTE[k % len(PALETTE)]
        vals = series[lab] or []
        pts = [(i, *to_xy(v, i)) for i, v in enumerate(vals)
               if isinstance(v, (int, float))]
        # nối chỉ các điểm LIÊN TIẾP — None là lỗ, đường đứt tại đó (T31)
        for a, b in zip(pts, pts[1:]):
            if b[0] == a[0] + 1:
                items.append(("line", color, a[1], a[2], b[1], b[2]))
        for _, x, y in pts:
            items.append(("dot", color, x, y))
        if pts:
            items.append(("label", pts[-1][1] + 4, pts[-1][2], lab[:16], "start"))
    return items


def rank_series_from_history(history: dict, width: int = CHART_WIDTH) -> dict:
    """{kw: [pos 8 mốc]} của kw đang theo dõi có hạng — xếp kw có hạng tốt (số
    nhỏ) trước; kw chưa từng rank được bỏ (chart chỉ vẽ số đã đo)."""
    checks = (history or {}).get("checks") or {}
    stamps = sorted(checks.keys())[-width:]
    out = {}
    for s in stamps:
        for kw, entry in (checks[s] or {}).items():
            pos = (entry or {}).get("pos")
            if not isinstance(pos, int):
                continue
            series = out.setdefault(kw, [None] * len(stamps))
            idx = stamps.index(s)
            series[idx] = pos
    # đủ mốc: fill None cho kw thiếu mốc đầu
    for kw, series in out.items():
        while len(series) < len(stamps):
            series.insert(0, None)
    scored = {kw: s for kw, s in out.items()
              if any(isinstance(v, int) for v in s)}
    return dict(sorted(scored.items(),
                       key=lambda kv: min(v for v in kv[1] if isinstance(v, int))))


# ─── T31: AEO trend — % câu trả lời được nhắc theo tuần (0-100, cao = tốt) ──

def _iso_week(date_str: str) -> str:
    """'YYYY-MM-DD...' → 'YYYY-Wnn' (tuần ISO). Hỏng → ''."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(date_str or ""))
    if not m:
        return ""
    try:
        d = _date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return ""
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def aeo_trend_series(history: dict, weeks: int = 8) -> dict:
    """{"labels": [tuần ISO], "series": {label: [%]}} cho chart AEO — mỗi cột 1 TUẦN ISO.

    series: "AI nhắc (tổng)" = % câu trả lời dán trong tuần được nhắc brand
    (0-100, cao = tốt — chart KHÔNG đảo trục); mỗi engine hay dùng (≤3) 1 đường
    riêng. Tuần không dán câu nào → None (đường đứt, không tính 0% sai nghĩa).
    Ít nhất 2 tuần có dữ liệu mới đáng vẽ — caller kiểm tra trước.
    """
    records = (history or {}).get("records") or []
    buckets: dict[str, dict] = {}  # week -> {"all": [0/1...], engine: [0/1...]}
    for r in records:
        if not isinstance(r, dict):
            continue
        wk = _iso_week(r.get("date"))
        if not wk:
            continue
        b = buckets.setdefault(wk, {"all": []})
        eng = str(r.get("engine") or "?")
        b.setdefault(eng, []).append(1 if r.get("mentioned") else 0)
        b["all"].append(1 if r.get("mentioned") else 0)

    def _pct(vals: list):
        return round(100.0 * sum(vals) / len(vals)) if vals else None

    weeks_sorted = sorted(buckets)[-weeks:]
    # đủ trục x: chèn các tuần KHÔNG có dữ liệu giữa min..max (None = đường đứt)
    def _week_keys(weeks_list):
        out = []
        for wk in weeks_list:
            y, w = wk.split("-W")
            out.append((int(y), int(w)))
        return out

    if weeks_sorted:
        keys = _week_keys(weeks_sorted)
        all_weeks = []
        cur = keys[0]
        end = keys[-1]
        # đi tuần ISO kế tiếp (dựa ngày giữa tuần — lấy ngày 4 = thứ 5 để đúng năm ISO)
        while True:
            all_weeks.append(f"{cur[0]}-W{cur[1]:02d}")
            if cur == end:
                break
            mid = _date.fromisocalendar(cur[0], cur[1], 4)
            nxt = _date.fromisocalendar(*((mid.isocalendar()[0], mid.isocalendar()[1] + 1, 4)))
            cur = (nxt.isocalendar()[0], nxt.isocalendar()[1])
            if len(all_weeks) > weeks * 2:  # đai an toàn — week ISO không thể dài thế
                break
        weeks_sorted = all_weeks
    engines_all: Counter = Counter()
    for wk in weeks_sorted:
        for eng, vals in (buckets.get(wk) or {}).items():
            if eng != "all":
                engines_all[eng] += sum(vals)
    # chỉ vẽ engine có đủ nhắc gì đó trong window (top 3 + tổng) — tránh rừng đường
    top_engines = [e for e, _ in engines_all.most_common(3)]
    series: dict = {"AI nhắc (tổng)": [_pct((buckets.get(wk) or {}).get("all", []))
                                      for wk in weeks_sorted]}
    for eng in top_engines:
        vals = [_pct((buckets.get(wk) or {}).get(eng, [])) for wk in weeks_sorted]
        if any(v is not None for v in vals):
            series[eng] = vals
    # tuần ISO làm nhãn trục x (chart vẽ %, không phải tuần) — tách khỏi series
    return {"labels": list(weeks_sorted), "series": series}


def trend_compare(trend: dict) -> tuple:
    """T31 — so 2 tuần CÓ dữ liệu cuối cùng trong đường 'AI nhắc (tổng)':
    (pct_gần_nhất, pct_trước_đó, số_tuần_có_dữ_liệu). Ít hơn 2 tuần có dữ liệu
    → (None, None, n) — không đủ để nói trend, caller bỏ qua."""
    vals = ((trend or {}).get("series") or {}).get("AI nhắc (tổng)") or []
    got = [v for v in vals if isinstance(v, (int, float))]
    if len(got) < 2:
        return None, None, len(got)
    return got[-1], got[-2], len(got)


def trend_words(cur, prev) -> str:
    """T31 — 'tăng/giảm/đứng yên' so 2 mức; thiếu 1 mức → ''."""
    if cur is None or prev is None:
        return ""
    if cur > prev:
        return "tăng"
    if cur < prev:
        return "giảm"
    return "đứng yên"


def gsc_trend_series(history: dict, last: int = 8) -> dict:
    """T42 — {"labels": [ngày fetch], "clicks": [...], "imps": [...]} tổng từng
    mốc GSC snapshot (key = ngày fetch, rows.key tương ứng query). Ít nhất 2
    mốc mới đáng vẽ — caller kiểm tra len trước. 0 request mới — chỉ READ."""
    snaps = (history or {}).get("snapshots") or {}
    labels = sorted(snaps)[-last:]
    clicks, imps = [], []
    for k in labels:
        rows = (snaps[k] or {}).get("rows") or {}
        clicks.append(sum(int((r or {}).get("clicks") or 0) for r in rows.values()))
        imps.append(sum(int((r or {}).get("impressions") or 0)
                        for r in rows.values()))
    return {"labels": labels, "clicks": clicks, "imps": imps}


# ─── T59: PSI trend — điểm Core Web Vitals site qua các lần đo (0-100, cao = tốt) ──

def psi_trend_series(hist: list, width: int = CHART_WIDTH) -> dict:
    """T59 — từ lịch sử PSI (pagespeed.history_scores: [(at, {strategy: score})])
    → {"labels": [ngày 'MM-DD'], "series": {"mobile": [...], "desktop": [...]}}.
    Lấy `width` mốc gần nhất; strategy thiếu ở mốc nào là None (đường đứt — y như
    hole T31). Không đảo trục (invert_y=False ở caller) — điểm CAO = tốt.
    Caller tự kiểm ≥ 2 mốc; 0 request mới — chỉ đọc state đã lưu."""
    entries = (hist or [])[-width:]
    labels = []
    for at, _ in entries:
        s = str(at or "")
        labels.append(s[5:10] if len(s) >= 10 else (s or "?"))
    strategies = []
    for _, sc in entries:
        for k, v in (sc or {}).items():
            if isinstance(v, int) and k not in strategies:
                strategies.append(k)
    series = {s: [sc.get(s) if isinstance((sc or {}).get(s), int) else None
                  for _, sc in entries]
              for s in strategies}
    return {"labels": labels, "series": series}
