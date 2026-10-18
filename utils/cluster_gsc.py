# -*- coding: utf-8 -*-
"""utils/cluster_gsc.py — G-C1: cụm từ khóa × dữ liệu Google thật (GSC).

Đọc hai nguồn ĐÃ CÓ, 0 request mới, chỉ READ:
- cụm: utils.keyword_groups.build_clusters (token overlap giữa từ khóa đang theo dõi);
- GSC: snapshot Search Console mới nhất trong gsc_history.json (gsc_client.latest_gsc_rows).

Điều GSC trả lời mà SERP không: có được Google phơi trang cho cụm không,
phơi bao nhiêu, có click không — kể cả khi từ khóa chưa từng lọt Top 100
(lúc đó rank_tracker chỉ nhìn được chỗ trống).

Ba nhóm được liệt kê, mỗi cụm xuất hiện duy nhất một lần:
- **hoạt động tốt**: cụm có imps GSC — đang được Google phục vụ;
- **mù GSC**: cụm 0 imps toàn thành viên — viết identity chưa rõ, Google chọn
  trang khác hoặc chưa index; trong khi cụm mới tinh thì imps = 0 tự nhiên;
- **không vào cụm / không đo được**: từ khóa đơn độc (không đủ ≥
  CLUSTER_MIN_SHARED token chung) — nêu đích để phần trống không nghe như hỏng.
"""
from utils.gsc_client import latest_gsc_rows
from utils.keyword_groups import build_clusters, CLUSTER_MIN_SHARED

# imps GSC tối thiểu để một cụm được coi là "Google đang phơi" (dưới mốc là nhiễu)
MIN_CLUSTER_IMPS = 30


def build_rows(rows: dict = None, keywords: list = None) -> dict:
    """Ghép cụm với GSC. Returns:
    - "active": [{anchor, members, imps, clicks, ctr, pos}] imps giảm dần
      (chỉ đếm member CÓ biển hiện trong GSC; ctr/pos None khi không có);
    - "blind": [{anchor, members, n_kw}] cụm 0 imps toàn thành viên;
    - "loners": [kw] từ khóa không vào cụm nào (giữ nguyên thứ tự input);
    - "n_measureable": số member có biển hiện trong GSC (cả 2 nhóm) — báo cáo
      dùng để nói rõ phần trống là vì Google chưa phơi, không phải bug.
    Có thể dùng cả SAI khi chưa có dữ liệu: rows = {} → tất cả cụm là blind.
    """
    if rows is None:
        rows = latest_gsc_rows()
    if keywords is None:
        from utils.keywords import load_keywords
        keywords = load_keywords()

    active, blind = [], []
    n_measurable = 0
    clustered: set = set()
    for cluster in build_clusters(keywords or []):
        members = cluster["members"]
        clustered.update(members)
        present = [rows.get(m) for m in members if m in rows]
        if not present:
            blind.append({"anchor": cluster["anchor"], "members": members,
                          "n_kw": len(members)})
            continue
        imps = sum(int(r.get("impressions") or 0) for r in present)
        if imps <= 0:
            # vấn đề như blind — hiện trong rows nhưng 0 imps không đáng đếm
            blind.append({"anchor": cluster["anchor"], "members": members,
                          "n_kw": len(members)})
            continue
        n_measurable += len(present)
        clicks = sum(int(r.get("clicks") or 0) for r in present)
        n = len(present)
        ctr = clicks / imps if imps else None
        pos = sum(float(r.get("position") or 0) for r in present) / n if n else None
        active.append({"anchor": cluster["anchor"], "members": members,
                       "imps": imps, "clicks": clicks,
                       "ctr": ctr, "pos": pos, "n_measured": n})
    active.sort(key=lambda r: (-r["imps"], r["anchor"]))
    blind.sort(key=lambda r: (-r["n_kw"], r["anchor"]))
    loners = [kw for kw in (keywords or []) if kw not in clustered]
    return {"active": active, "blind": blind, "loners": loners,
            "n_measurable": n_measurable}


def report_text(rows: dict, min_imps: int = MIN_CLUSTER_IMPS) -> str:
    """(Bản text — caller tự in). Trống cusm/rows → tự nói thứ cần chạy."""
    active = rows.get("active") or []
    blind = rows.get("blind") or []
    loners = rows.get("loners") or []

    if not active and not blind and not loners:
        return ("  Chưa có từ khóa theo dõi nào — thêm vào config/keywords.json"
                "\n  rồi chạy --rank / --gsc để có dữ liệu.")

    lines = [f"  CỤM TỪ KHÓA × GSC (Google thật, 28 ngày)",
             "  " + "-" * 100]
    if active:
        lines.append(f"  CỤM ĐANG ĐƯỢC GOOGLE PHƠI ({len(active)} cụm):")
        lines.append(f"  {'Cụm (anchor)':<34}{'n_kw':>5}{'Imps':>7}{'Clicks':>7}"
                     f"{'CTRTB':>7}{'Vị trí TB':>10}")
        for r in active:
            ctr = f'{r["ctr"] * 100:.1f}%' if r["ctr"] is not None else "—"
            pos = f'{r["pos"]:.1f}' if r["pos"] is not None else "—"
            fb = f" ({r['n_measured']}/{r['n_kw'] or len(r['members'])} kw GSC biết)" \
                 if r["n_measured"] < len(r["members"]) else ""
            lines.append(f'  {r["anchor"][:34]:<34}{len(r["members"]):>5}'
                         f'{r["imps"]:>7}{r["clicks"]:>7}{ctr:>7}{pos:>10}{fb}')
        lines.append("  n_kw = số member của cụm; imps/clicks = tổng member GSC thấy;"
                             " CTR/vị trí = trung bình các member GSC đo được.")
    else:
        lines.append("  Không cụm nào có imps GSC ≥ 1 — Google chưa phơi trang cho "
                     "cụm nào (hoặc chưa fetch --gsc).")

    if blind:
        lines.append("")
        lines.append(f"  CỤM MÙ GSC ({len(blind)} cụm — Google CHƯA phơi cho keyword nào"
                     " trong cụm):")
        for r in blind:
            extra = "; ".join(m for m in r["members"] if m != r["anchor"])
            tail = f"  (+{r['n_kw'] - 1}: {extra})" if extra else ""
            lines.append(f'  • "{r["anchor"][:34]}"{tail}')
        lines.append("  Mục này CHƯA hẳn là lỗi: cụm mới viết / chưa index là imps = 0"
                     " tự nhiên. Cụm cũ mà vẫn mù → cần xem lại identity bài viết"
                     " (Google chọn trang khác).")

    if loners:
        lines.append("")
        lines.append(f"  KHÔNG VÀO CỤM NÀO ({len(loners)} từ khóa — cần ≥ "
                     f"{CLUSTER_MIN_SHARED} token chung):")
        lines.append("  " + "; ".join(loners[:15]) +
                     ("…" if len(loners) > 15 else ""))
    lines.append("  " + "-" * 100)
    lines.append("  Nguồn: GSC 28 ngày × cụm token-overlap. Cụm = 1 bài/nhóm bài;"
                 " cụm mù sau một thời gian dài là gợi ý viết/refresh sớm.")
    return "\n".join(lines)


def run_cluster_gsc_cli() -> int:
    """`--cluster-gsc`: hiệu năng cụm theo dữ liệu Google thật."""
    import config.settings as cfg

    text = report_text(build_rows())
    print("=" * 104)
    print(f"  CỤM × GSC — {getattr(cfg, 'TARGET_URL', '') or '(chưa cấu hình site)'}")
    print("=" * 76)
    print(text)
    print("=" * 104)
    return 0
