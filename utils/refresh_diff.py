# -*- coding: utf-8 -*-
"""utils/refresh_diff.py — F10g: `--refresh-diff` — bài refresh lỡ hẹn ở đâu.

Mục `--keyword-groups` đã nói **AI nào nên refresh** (từng top-10, đang tụt
về 5..15). Bước kế tiếp người quản cũng hỏi: **refresh mà chưa làm — tại sao,
cần gì để làm**. Lệnh này ghép danh sách refresh với trạng thái thực tế:

1. **CHƯA CÓ DRAFT** — kw trong danh sách nhưng `content/drafts/` không có file
   nào khớp (fold không dấu) → chưa viết gì cả: việc là viết lại draft.
2. **CÓ DRAFT CHỜ DUYỆT** — có draft chưa push WP → việc là duyệt + `--wp-push`.
3. **ĐÃ PUSH WP** — có trong `data/wp_pushed.json` → xem ngày push; nếu push từ
   trước mốc rank tụt gần nhất thì "refresh đã chạy nhưng chưa kịp ăn", nếu
   sau thì refresh xong vẫn tụt tiếp → cấu trúc bài vấn đề (mức nặng hơn).

Mọi thứ đọc lại state có sẵn (rank history + drafts + wp_pushed), 0 request,
0 mạng. Chỉ READ — quyết định refresh ra sao thuộc về owner.
"""
def _fold_kw(value: str) -> str:
    """Fold không dấu — bản duy nhất của repo (plan_progress dùng cùng hàm)."""
    from utils.plan_progress import _fold_kw
    return _fold_kw(value)

def build_diff(refresh_rows: list, drafts: dict, pushed: dict) -> list:
    """Mỗi bài refresh + trạng thái {state, advice, draft_file, pushed_link}.

    state: 'chua_draft' | 'cho_duyet' | 'da_push'. Không list refresh → [].
    """
    out = []
    for r in (refresh_rows or []):
        kw = str(r.get("keyword") or "").strip()
        if not kw:
            continue
        key = _fold_kw(kw)
        entry = drafts.get(key) if drafts else None
        push = pushed.get(key) if pushed else None
        if push:
            state, advice = "da_push", "refresh đã push — theo dõi hạng 2 lần check kế trước khi đụng tay"
        elif entry:
            state = "cho_duyet"
            advice = "draft CHỜ DUYỆT — đọc, duyệt rồi --wp-push"
        else:
            state, advice = "chua_draft", "chưa có draft — viết lại bài (dùng --keyword-groups list làm outline)"
        out.append({**r, "state": state, "advice": advice,
                    "draft_file": entry.get("file", "") if entry else "",
                    "pushed_link": str(push.get("link") or "") if push else ""})
    # việc gấp trước: chưa làm gì > chờ duyệt > đã làm (theo dõi)
    rank = {"chua_draft": 0, "cho_duyet": 1, "da_push": 2}
    out.sort(key=lambda x: (rank[x["state"]], -(x["current"] - x["best_ever"])))
    return out


def diff_text(rows: list) -> str:
    if not rows:
        return ("  Không bài nào trong danh sách refresh (từng top-10, đang tụt 5..15) — "
                "chạy --rank đủ 2 lần rồi --keyword-groups.")
    labels = {"chua_draft": "CHƯA CÓ DRAFT", "cho_duyet": "CÓ DRAFT CHỜ DUYỆT",
              "da_push": "ĐÃ PUSH WP"}
    icons = {"chua_draft": "✍️", "cho_duyet": "⏳", "da_push": "👀"}
    lines = [f"  REFRESH LỠ HẸN Ở BƯỚC NÀO ({len(rows)} bài):",
             "  " + "-" * 70]
    for r in rows:
        st = r.get("state")
        lines.append(f'  {icons.get(st, "·")} {labels.get(st, st):<18} '
                     f'"{r["keyword"][:34]}"  hạng {r["best_ever"]} → {r["current"]}')
        lines.append(f'    ▸ {r.get("advice", "")}')
    lines.append("  " + "-" * 70)
    lines.append("  TỔNG: " + ", ".join(
        f'{labels[s].lower()}: {sum(1 for r in rows if r["state"] == s)}'
        for s in ("chua_draft", "cho_duyet", "da_push")))
    lines.append("  Sửa ra sao là quyết định của owner — list này chỉ xếp việc")
    return "\n".join(lines)


def run_refresh_diff_cli() -> int:
    """`--refresh-diff`: danh sách refresh × thủ tục thực tế xong đến bước nào."""
    import config.settings as cfg
    from utils.keyword_groups import build_refresh_list
    from utils.rank_tracker import _load_history
    from utils.plan_progress import scan_drafts, load_pushed
    from utils.alerts import _log

    history = _load_history()
    refresh_rows = build_refresh_list(history)
    if not refresh_rows:
        print("=" * 104)
        print(f"  REFRESH DIFF — {getattr(cfg, 'TARGET_URL', '') or '(chưa cấu hình site)'}")
        print("=" * 76)
        print("  Không bài nào trong danh sách refresh — từng top-10 mới tính;")
        print("  chạy --rank đủ 2 lần rồi --keyword-groups để xem danh sách gốc.")
        print("=" * 104)
        return 0
    try:
        drafts = scan_drafts()
    except Exception as e:
        drafts = {}
        _log(f"[RefreshDiff] phần draft bỏ qua: {type(e).__name__}: {e}")
    try:
        pushed = load_pushed()
    except Exception as e:
        pushed = {}
        _log(f"[RefreshDiff] phần wp_pushed bỏ qua: {type(e).__name__}: {e}")

    rows = build_diff(refresh_rows, drafts, pushed)
    print("=" * 104)
    print(f"  REFRESH DIFF — {getattr(cfg, 'TARGET_URL', '') or '(chưa cấu hình site)'}")
    print("=" * 76)
    print(diff_text(rows))
    print("=" * 104)
    return 0
