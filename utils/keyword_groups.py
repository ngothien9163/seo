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
    print("=" * 76)
    return 0
