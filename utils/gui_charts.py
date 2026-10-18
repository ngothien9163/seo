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
"""
CHART_WIDTH = 8          # dùng 8 mốc gần nhất, khớp TREND_WIDTH của gsc-trend
CHART_MARGIN = 28        # lề cho nhãn
TOP_KEYWORDS = 5         # nhiều hơn là rối — vẽ tối đa 5 đường

PALETTE = ("#4fc3f7", "#81c784", "#ffb74d", "#e57373", "#ba68c8")
INK = "#cfcfd8"
GRID = "#3a3a44"


def chart_items(series: dict, w: int, h: int, invert_y: bool = True) -> list:
    """THUẦN: {label: [giá trị mốc]} → item canvas.

    invert_y=True (rank): giá trị NHỎ ở TRÊN (hạng 1 = đỉnh). Giá trị None là lỗ — đường đứt tại đó (nối từng đoạn liên tục).
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
        y = y_top + (y_bottom - y_top) * frac
        if invert_y:
            y = y_bottom - (y_bottom - y_top) * frac
        return x, y

    items = []
    # lưới ngang: min / giữa / max
    for gv, gy in ((lo, y_bottom if invert_y else y_top),
                   ((lo + hi) / 2, (y_top + y_bottom) / 2),
                   (hi, y_top if invert_y else y_bottom)):
        items.append(("grid", gy, f"{gv:g}"))
    for k, lab in enumerate(labels):
        color = PALETTE[k % len(PALETTE)]
        vals = series[lab] or []
        pts = [to_xy(v, i) for i, v in enumerate(vals)
               if isinstance(v, (int, float))]
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            items.append(("line", color, x1, y1, x2, y2))
        for x, y in pts:
            items.append(("dot", color, x, y))
        if pts:
            items.append(("label", pts[-1][0] + 4, pts[-1][1], lab[:16], "start"))
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
