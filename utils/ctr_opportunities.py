# -*- coding: utf-8 -*-
"""utils/ctr_opportunities.py — G-1: CTR cơ hội từ Search Console.

Đọc snapshot GSC gần nhất (0 request mới, 0 ghi file): query đang thấy trên
SERP (CTR_POS_LO..CTR_POS_HI) mà CTR thấp hơn CTR bình quân của chính nhóm
query đó → gợi ý viết lại title/meta description.

Baseline là các query trong CÙNG vùng vị trí (đủ impressions): so query hạng 5
với query hạng 20 là sai — CTR tự nhiên giảm theo hạng, ghép vào bìnhquin sẽ
kéo mốc xuống và che mất query có vấn đề.
Query không đủ impressions (CTR_MIN_IMPRESSIONS) bị loại — CTR của vài imps
là nhiễu, không phải tín hiệu.

Ý: Google đã cho khách thấy mình, khách không click → tiêu đề/mô tả chưa chốt
được khách. Sửa được bằng tay trên site, không cần đợi xếp hạng.
"""
from utils.gsc_client import latest_gsc_rows

CTR_POS_LO = 1            # hạng hiện tại trong khoảng [LO..HI] = 'đang thấy trên SERP'
CTR_POS_HI = 11           # qua mốc 10 = lẻo sang trang 2 — title đổi còn được click
CTR_MIN_IMPRESSIONS = 30  # dưới mốc này CTR là nhiễu, không đưa ra khuyến nghị


def _qualified(rows: dict, in_band_only: bool) -> list[dict]:
    """Rows đủ điều kiện (đủ impressions; in_band_only → thêm cùng vùng vị trí)."""
    out = []
    for r in (rows or {}).values():
        r = r or {}
        imp = int(r.get("impressions") or 0)
        pos = float(r.get("position") or 0.0)
        if imp < CTR_MIN_IMPRESSIONS:
            continue
        if in_band_only and not (CTR_POS_LO <= pos <= CTR_POS_HI):
            continue
        out.append(r)
    return out


def avg_ctr(rows: dict, min_impressions: int = 0) -> float:
    """CTR bình quân (%) mọi query đủ `min_impressions` — helper chung; engine
    so bằng band_avg_ctr (baseline trong-band), KHÔNG dùng mốc này."""
    vals = [float(r.get("ctr") or 0.0) * 100.0
            for r in (rows or {}).values()
            if int(r.get("impressions") or 0) >= min_impressions]
    return round(sum(vals) / len(vals), 2) if vals else 0.0


def band_avg_ctr(rows: dict) -> float:
    """CTR bình quân (%) các query CÙNG vùng vị trí + đủ impressions — mốc đối
    chiếu của engine. Nhóm rỗng → 0.0 (không so được, caller phải xử)."""
    vals = [float(r.get("ctr") or 0.0) * 100.0 for r in _qualified(rows, True)]
    return round(sum(vals) / len(vals), 2) if vals else 0.0


def build_opportunities(rows: dict) -> list[dict]:
    """{query, position, impressions, clicks, ctr_pct, avg_pct, gap} — query
    đang trong vùng vị trí mà CTR thua bình quân của nhóm. Xếp theo
    impressions giảm; và query có CTR >= bình quân không phải 'cơ hội'."""
    rows = rows or {}
    if not rows:
        return []
    avg = band_avg_ctr(rows)
    if avg <= 0:
        return []

    out = []
    for q, r in rows.items():
        r = r or {}
        imp = int(r.get("impressions") or 0)
        pos = float(r.get("position") or 0.0)
        if imp < CTR_MIN_IMPRESSIONS or not (CTR_POS_LO <= pos <= CTR_POS_HI):
            continue
        ctr_pct = float(r.get("ctr") or 0.0) * 100.0
        if ctr_pct >= avg:
            continue      # đang đón khách tốt hơn bình quân — không phải "cơ hội"
        out.append({"query": str(q),
                    "position": pos,
                    "impressions": imp,
                    "clicks": int(r.get("clicks") or 0),
                    "ctr_pct": round(ctr_pct, 1),
                    "avg_pct": avg,
                    "gap": round(avg - ctr_pct, 1)})
    out.sort(key=lambda r: (-r["impressions"], r["position"], r["query"]))
    return out


def report_text(rows: dict) -> tuple[str, int]:
    """(text, số query được gợi ý). Chưa từng fetch GSC → gợi ý lệnh cần chạy."""
    if not rows:
        return ("  Chưa có snapshot Search Console nào — chạy `python main.py --gsc`"
                "\n  rồi xem lại. CTR cơ hội tính trên dữ liệu Google thật,"
                "\n  rank tracker không đo được điều này."), 0

    opps = build_opportunities(rows)
    if not opps:
        avg = band_avg_ctr(rows)
        msg = (f"  Không query nào gợi ý được — CTR bình quân các query trong vùng"
               f" vị trí (hạng {CTR_POS_LO}..{CTR_POS_HI},"
               f" ≥ {CTR_MIN_IMPRESSIONS} impressions) là {avg:.1f}%"
               "\n  và không query nào thua mức đó (hoặc nhóm chưa đủ dữ liệu).")
        return msg, 0

    lines = [f"  CTR CƠ HỘI ({len(opps)} query — thấy trên SERP mà ít người click)",
             "  " + "-" * 68,
             f"  {'Query':<34}{'Hạng':>6}{'Imps':>7}{'Clicks':>7}{'CTR':>8}"
             f"{'TB':>7}{'Chênh':>8}"]
    for r in opps:
        lines.append(f'  {r["query"][:34]:<34}{r["position"]:>6.1f}'
                     f'{r["impressions"]:>7}{r["clicks"]:>7}'
                     f'{r["ctr_pct"]:>7.1f}%{r["avg_pct"]:>6.1f}%'
                     f'{r["gap"]:>8.1f}%')
    lines.append("  " + "-" * 68)
    lines.append("  CTR thấp hơn bình quân của nhóm cùng vị trí = title/mô tả")
    lines.append("  chưa chốt được khách. Viết lại title/meta description trang")
    lines.append("  tương ứng — lợi ích rõ, từ khóa chính lên đầu.")
    lines.append("  TB = CTR bình quân các query cùng vùng vị trí, đủ impressions.")
    return "\n".join(lines), len(opps)


def run_ctr_cli() -> int:
    """`--ctr-ops`: bảng query nên sửa title/meta, đọc từ snapshot GSC có sẵn."""
    import config.settings as cfg

    rows = latest_gsc_rows()
    text, n = report_text(rows)
    print("=" * 76)
    print(f"  CTR CƠ HỘI — {cfg.TARGET_URL or '(chưa cấu hình site)'}")
    print("=" * 76)
    print(text)
    print("=" * 76)
    return 0
