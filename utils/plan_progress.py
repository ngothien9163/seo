# -*- coding: utf-8 -*-
"""utils/plan_progress.py — C-3: tiến độ content plan 30 ngày.

Map DEFAULT_30D_PLAN với dữ liệu đã có (0 request, 0 mạng):
- **draft đã sinh**: frontmatter của file .md trong content/drafts/ —
  khớp plan item theo keyword (fold không dấu, y hệt kỹ thuật GSC).
- **đã push WP**: data/wp_pushed.json — wp push_file thành công tự ghi
  1 bản {kw→{id, link, pushed_at}}. State này wp_publisher tự giữ.

Chỉ READ — không sinh, không đẩy; gợi ý lệnh --generate cho mục còn trống.
"""
import os
import re
import json
import datetime

from content.planner import DEFAULT_30D_PLAN
from content.generator import drafts_dir
from utils.wp_publisher import _strip_frontmatter

import config.settings as cfg
import utils.site_paths as _sp

WP_PUSHED_NAME = "wp_pushed.json"


def _pushed_path() -> str:
    """data/wp_pushed.json (per-site khi migrate) — một điểm duy nhất."""
    return _sp.per_site(WP_PUSHED_NAME, os.path.join(_sp.ROOT, "data"))


def load_pushed() -> dict:
    try:
        with open(_pushed_path(), encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def save_pushed(state: dict) -> None:
    path = _pushed_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def mark_pushed(keyword: str, wp_id, link: str = "", when: str = "") -> None:
    """wp push_file thành công GỌI THÊM — key là keyword sau fold (trùng kw
    nhiều draft chỉ cần 1 dấu đã push)."""
    state = load_pushed()
    key = _fold_kw(keyword)
    if key:
        state[key] = {"keyword": keyword, "id": wp_id, "link": link,
                      "pushed_at": when or datetime.datetime.now().isoformat(
                          timespec="seconds")}
    save_pushed(state)


# ─── FOLD: một nguồn duy nhất — dùng _fold của gsc_client ────────────────────

def _fold_kw(value: str) -> str:
    from utils.gsc_client import _fold
    return _fold(value)


def scan_drafts(out_dir: str = None) -> dict:
    """Đọc frontmatter từng file .md trong drafts → {kw_fold: {file, keyword, type, date}}.
    File lỗi/frontmatter rác bị bỏ qua — quét lỗi không được dead report."""
    out_dir = out_dir or drafts_dir()
    if not os.path.isdir(out_dir):
        return {}
    out = {}
    for name in sorted(os.listdir(out_dir)):
        if not name.lower().endswith(".md"):
            continue
        try:
            text = open(os.path.join(out_dir, name), encoding="utf-8").read()
        except OSError:
            continue
        meta, body = _strip_frontmatter(text)
        kw = str(meta.get("keyword") or "").strip()
        key = _fold_kw(kw)
        if not key:
            continue   # không biết keyword là gì — không đếm là draft
        # 1 kw ~= 1 concept; draft luôn ra file mới nếu chạy lại — lấy mốc MỚI NHẤT
        st = out.get(key)
        date = str(meta.get("date") or "")
        if st is None or date >= st.get("date", ""):
            out[key] = {"file": name, "keyword": kw,
                        "type": str(meta.get("type") or ""),
                        "date": date}
    return out


# ─── BÁO CÁO ─────────────────────────────────────────────────────────────────

def build_progress(plan: list = None, drafts: dict = None,
                   pushed: dict = None) -> list[dict]:
    """[item] {day, keyword, type, has_draft, pushed} — một mốc cho 30 ngày plan."""
    drafts = drafts if drafts is not None else scan_drafts()
    pushed = pushed if pushed is not None else load_pushed()
    out = []
    for item in (plan or DEFAULT_30D_PLAN):
        key = _fold_kw(item.get("keyword") or "")
        out.append({**item,
                    "has_draft": key in drafts,
                    "pushed": key in pushed})
    return out


def report_text(rows: list) -> tuple[str, int]:
    """(text, số ngày còn trống). Không plan → hướng dẫn plan từ planner."""
    if not rows:
        return ("  Content plan 30 ngày trống — xem content/planner.py "
                "DEFAULT_30D_PLAN.", 0)
    with_draft = [r for r in rows if r["has_draft"]]
    pushed = [r for r in rows if r["pushed"]]
    lines = [
        f"  TIẾN ĐỘ CONTENT PLAN 30 NGÀY — draft {len(with_draft)}/{len(rows)}"
        f" | đã push WP {len(pushed)}",
        "  " + "-" * 92,
        f"  {'Ngày':>4}  {'Loại':<7}{'Trạng thái':<16}{'Từ khóa'}"]
    for r in rows:
        if r["pushed"]:
            mark, note = "✓✓", "đã push WP"
        elif r["has_draft"]:
            mark, note = " ✓", "draft chờ duyệt"
        else:
            mark, note = "  ", ""
        lines.append(f'  {r["day"]:>4}. {r.get("type", ""):<7}{mark:>2} {note:<10}'
                     f'  {r.get("keyword", "")}')
    lines.append("  " + "-" * 92)
    if len(with_draft) < len(rows):
        next_free = next(r for r in rows if not r["has_draft"])
        lines.append(f'  Mục kế tiếp còn trống: ngày {next_free["day"]} —'
                     f' python main.py --generate --day {next_free["day"]}')
    done = len(pushed)
    if done < len(with_draft):
        lines.append(f'  {len(with_draft) - done} draft CHỜ DUYỆT — python main.py --wp-push '
                     'content/drafts/<file>.md (tool chỉ đẩy draft/pending).')
    lines.append("  ✓ = draft sinh, chuẩn bị duyệt tay; ✓✓ = đã đẩy WP (vẫn KHÔNG tự publish).")
    return "\n".join(lines), len(rows) - len(with_draft)


def run_plan_progress_cli() -> int:
    """`--plan-progress`: 30 mục plan → draft sinh? / đã push WP?"""
    import config.settings as _
    rows = build_progress()
    text, remaining = report_text(rows)
    print("=" * 96)
    print(f"  PLAN PROGRESS — {cfg.TARGET_URL or '(chưa cấu hình site)'}")
    print("=" * 96)
    print(text)
    print("=" * 96)
    return 0
