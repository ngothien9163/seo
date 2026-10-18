# -*- coding: utf-8 -*-
"""utils/keyword_groups.py — P2-2: cụm từ khóa + danh sách bài nên refresh.

KHÔNG mạng, KHÔNG ghi file gì — đọc hai nguồn đã có:
- Clusters: token overlap giữa các từ khóa đang theo dõi (dùng lại
  utils.audit_actions._kw_tokens — một nguồn duy nhất cho fold/stopword).
- Refresh: rank history — kw hiện tại hạng 5..15 (REFRESH_POS_HI..HI) nhưng
  TỪNG có hạng ≤ REFRESH_EVER_TOP: trang đã từng top-10, đang tụt dần
  → cập nhật nội dung là rẻ hơn viết mới.
"""
from utils.audit_actions import _kw_tokens

CLUSTER_MIN_SHARED = 2      # >= N token riêng chung mới coi là cùng cụm
REFRESH_POS_LO = 5          # hạng hiện tại trong khoảng [LO..HI] = 'đang lơi hạng'
REFRESH_POS_HI = 15
REFRESH_EVER_TOP = 10       # từng đạt <= mốc này → 'từng top-10'


def _anchor(sorted_kws: list) -> str:
    """Từ khóa nhiều token nhất làm tên cụm — cụ thể hơn chiếm tên."""
    return max(sorted_kws, key=lambda k: len(_kw_tokens(k)))


def build_clusters(keywords: list) -> list[dict]:
    """{anchor, members} — kw gộp cụm khi chia sẻ >= CLUSTER_MIN_SHARED token riêng
    với anchor. Kw đã vào cụm không tạo cụm mới (một kw = một cụm duy nhất,
    cụm sớm (thứ tự input) trước). Kw đơn độc không lập cụm."""
    out = []
    used = set()
    for kw in keywords or []:
        base = _kw_tokens(kw)
        if not base or kw in used:
            continue
        base_set = frozenset(base)
        members = []
        for other in (keywords or []):
            if other == kw or other in used:
                continue
            shared = base_set & frozenset(_kw_tokens(other))
            if len(shared) >= CLUSTER_MIN_SHARED:
                members.append(other)
        if len(members) >= 1:
            used.update(members)
            used.add(kw)
            group = [kw] + members
            out.append({"anchor": _anchor(group), "members": sorted(group)})
    return out


def _positions(checks: dict, stamps: list, kw: str) -> list[int]:
    return [((checks[s] or {}).get(kw) or {}).get("pos")
            for s in stamps if s in checks]


def build_refresh_list(history: dict) -> list[dict]:
    """kw 'đang lơi h hạng 5..15' + 'từng đạt top REFRESH_EVER_TOP' → gợi ý refresh
    {keyword, current, best_ever}. Không có data → [] (nguồn khác phải tự nói)."""
    checks = history.get("checks") or {}
    stamps = sorted(checks.keys())
    if len(stamps) < 2:
        return []
    cur_stamp, prev_stamps = stamps[-1], stamps[:-1]
    out = []
    for kw, cur_entry in (checks[cur_stamp] or {}).items():
        cur = (cur_entry or {}).get("pos")
        if not isinstance(cur, int) or not (REFRESH_POS_LO <= cur <= REFRESH_POS_HI):
            continue
        best = None
        for s in prev_stamps:
            p = ((checks[s] or {}).get(kw) or {}).get("pos")
            if isinstance(p, int) and (best is None or p < best):
                best = p
        if best is not None and best <= REFRESH_EVER_TOP:
            out.append({"keyword": kw, "current": cur, "best_ever": best})
    out.sort(key=lambda r: (r["current"] - r["best_ever"], r["keyword"]), reverse=True)
    return out


def clusters_text(clusters: list) -> str:
    if not clusters:
        return ("  Không cụm nào đủ điều (cần ≥ 2 từ khóa chia sẻ ≥ "
                f"{CLUSTER_MIN_SHARED} token riêng).\n"
                "  Nếu từ khóa đang theo dõi là cụm dài khó ghép — thường là dấu hiệu"
                " chúng phủ nhiều chủ đề, cụm nhỏ mới ghép được.")
    lines = [f"  CỤM TỪ KHÓA ({len(clusters)} cụm) — 1 cụm ≈ 1 bài / 1 nhóm bài hỗ trợ nhau",
             "  " + "-" * 68]
    for c in clusters:
        others = [m for m in c["members"] if m != c["anchor"]]
        lines.append(f'  • "{c["anchor"]}"' + (f'  (+{len(others)}: {"; ".join(others)})'
                                              if others else ""))
    lines.append("  Viết bài cho anchor và link nội bộ tới bài của member — xem --internal-links.")
    return "\n".join(lines)


def refresh_text(rows: list, n_checks: int = 0) -> str:
    if not rows:
        return ("  Chưa có kw nào rơi vào vùng refresh (hiện 5..15 + từng top-10).\n"
                + ("  " if n_checks >= 2 else
                   "  Lịch sử còn ít mốc — --rank chạy thêm vài lần sẽ đủ nhìn xu hướng.\n  "))
    lines = [f"  NÊN REFRESH ({len(rows)} bài) — từng top-10, đang tụt về giữa trang:",
             "  " + "-" * 68,
             f"  {'Từ khóa':<40}{'Hiện tại':>9}{'Từng đạt':>10}"]
    for r in rows:
        lines.append(f'  {r["keyword"][:40]:<40}{r["current"]:>9}{r["best_ever"]:>10}')
    lines.append("  Refresh = cập nhật bài cũ (thêm ý mới, sửa số liệu) — rẻ hơn viết mới.")
    return "\n".join(lines)


# ─── HIỆU NĂNG THEO CỤM (P3-2) ───────────────────────────────────────────────

TOP10 = 10


def cluster_performance(history: dict, keywords: list) -> list[dict]:
    """Gộp hạng theo cụm (dùng lại build_clusters):
    {anchor, members, n_kw, top10, avg_pos, trend, n_measured}
    - top10: số member mốc MỚI NHẤT đang Top TOP10 (pos None không đếm);
    - avg_pos: hạng trung bình các member có số (1 dấu thập phân, None nếu chịu);
    - trend: '+' mốc mới tốt hơn mốc trước (hạng trung bình nhỏ hơn),
      '-' xấu hơn, '=' giữ / không so được (chỉ 1 mốc, cụm không có số liên tiếp).
    Sắp top10 giảm → avg_pos tăng → anchor. Không những thế, kw char ở mốc không có
    (pos None) vẫn đếm trong n_kw — trend chỉ tính trên member có số.
    """

    checks = history.get("checks") or {}
    stamps = sorted(checks.keys())
    if not stamps or not keywords:
        return []
    latest = checks[stamps[-1]] or {}
    prev = (checks[stamps[-2]] or {}) if len(stamps) >= 2 else {}

    out = []
    for cluster in build_clusters(keywords):
        members = cluster["members"]
        cur_positions = [((latest.get(m) or {}).get("pos")) for m in members]
        top10 = sum(1 for p in cur_positions if isinstance(p, int) and p <= TOP10)
        known = [p for p in cur_positions if isinstance(p, int)]
        prev_positions = [((prev.get(m) or {}).get("pos")) for m in members]
        prev_known = [p for p in prev_positions if isinstance(p, int)]
        avg_cur = round(sum(known) / len(known), 1) if known else None
        avg_prev = round(sum(prev_known) / len(prev_known), 1) if prev_known else None
        trend = "="
        if avg_cur is not None and avg_prev is not None and avg_cur != avg_prev:
            trend = "+" if avg_cur < avg_prev else "-"
        out.append({"anchor": cluster["anchor"], "members": members,
                    "n_kw": len(members), "top10": top10,
                    "avg_pos": avg_cur, "trend": trend,
                    "n_measured": len(known)})
    out.sort(key=lambda r: (-r["top10"], r["avg_pos"] if r["avg_pos"] is not None else 999,
                            r["anchor"]))
    return out


def performance_text(rows: list, n_checks: int = 0, keywords: list = None) -> str:
    if not rows and not keywords:
        return "  Chưa có cụm nào hợp lệ — cụm cần ≥ 2 kw chia sẻ ≥ CLUSTER_MIN_SHARED token."
    if not rows and keywords:
        if n_checks < 1:
            return ("  Hiệu năng theo cụm chưa có — chưa có mốc xếp hạng nào."
                    "\n  Chạy `python main.py --rank` rồi xem lại.")
        # clusters truy được mà rows rỗng: mots kw check không có trong cụm → lạ, hiếm
        return "  Chưa có cụm nào hợp lệ — cụm cần ≥ 2 kw chia sẻ ≥ CLUSTER_MIN_SHARED token."
    lines = [f"  HIỆU NĂNG THEO CỤM ({len(rows)} cụm, mốc mới nhất)",
             "  " + "-" * 68,
             f"  {'Cụm (anchor)':<34}{'n_kw':>5}{'Top10':>6}{'Hạng TB':>8}{'Δ':>2}"]
    for r in rows:
        avg = f'{r["avg_pos"]:.1f}' if r["avg_pos"] is not None else "—"
        partial = f' ({r["n_measured"]}/{r["n_kw"]} kw có số)' if r["n_measured"] < r["n_kw"] else ""
        lines.append(f'  {r["anchor"][:34]:<34}{r["n_kw"]:>5}{r["top10"]:>6}{avg:>8}{r["trend"]:>2}{partial}')
    lines.append("  Top10 = số kw của cụm đang trong Top 10; Δ + = cụm đang tốt lên, - = xấu đi.")
    return "\n".join(lines)


def run_keyword_groups_cli() -> int:
    """`--keyword-groups`: cụm + refresh, đọc từ dữ liệu có sẵn."""
    import config.settings as cfg
    from utils.keywords import load_keywords
    from utils import rank_tracker as rt

    keywords = load_keywords()
    clusters = build_clusters(keywords)
    history = rt._load_history()
    n_checks = len(history.get("checks") or {})
    rows = build_refresh_list(history)

    print("=" * 76)
    print(f"  NHÓM TỪ KHÓA — {cfg.TARGET_URL or '(chưa cấu hình site)'}")
    print("=" * 76)
    print(clusters_text(clusters))
    print()
    print(refresh_text(rows, n_checks=n_checks))
    perf = cluster_performance(history, keywords)
    print()
    print(performance_text(perf, n_checks=n_checks, keywords=keywords))
    print("=" * 76)
    return 0
