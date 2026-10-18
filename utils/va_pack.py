# -*- coding: utf-8 -*-
"""utils/va_pack.py — F10j: `--va-pack` — gói hand-off cho trợ lý (VA).

Owner thuê trợ lý (VA) làm việc hàng ngày không muốn đào qua 10 lệnh CLI.
Lệnh này gói **toàn bộ việc người VA cần làm hôm nay** thành MỘT file
markdown đọc bằng điện thoại cũng được:

1. **Việc nội dung** — mục plan 30 ngày còn trống (kèm lệnh --generate),
   draft chờ duyệt (--wp-push), bài nên refresh và đã đến bước nào.
2. **Việc kỹ thuật** — query Google muốn mà site chưa có trang (content-gap,
   chỉ đoạn gợi ý tóm tắt, không liệt kê đuôi), đề xuất sửa title/meta (ctr-ops).
3. **Nền tảng** — tình trạng răng backlink (còn sống / báo lỗi), số câu auditor
   lưu ý từ audit gần nhất.

Mỗi nguồn bọc riêng — thiếu nguồn nào nguồn đó tự nói "chưa có dữ liệu",
không chết cả gói. KẾT QUẢ **GHI FILE** `data/<slug>/va_pack_<ngày>.md`
(atomic) và in đường dẫn — đây là file cho người, khác báo cáo Telegram 1-tin.
Không tự sửa gì, không tự publish gì.
"""
import os
from datetime import date

VA_SECTION_BLANK = "_(chưa có dữ liệu — mục này không có việc)_"

def _note(text: str) -> str:
    lines = [ln for ln in (text or "").strip().splitlines() if ln.strip()]
    return "\n".join("  " + ln.strip() for ln in lines) if lines else VA_SECTION_BLANK

def _section(title: str, body: str) -> list:
    return [f"## {title}", "", (body or "").strip() or VA_SECTION_BLANK, ""]

def build_plan_section(plan_rows: list) -> str:
    """Việc nội dung: mục trống + draft chờ duyệt (khác daily-report: VA cần
   LIỆT KÊ đủ, không cắt 5 — file md không giới hạn ký tự)."""
    from utils.daily_report import build_todo_lines
    lines = build_todo_lines(plan_rows or [])
    if not lines:
        return VA_SECTION_BLANK
    # thay hướng cắt tails vì file md đủ rộng: liệt kê toàn bộ todo
    todo = [r for r in (plan_rows or []) if not r.get("pushed") and not r.get("has_draft")]
    waiting = [r for r in (plan_rows or []) if r.get("has_draft") and not r.get("pushed")]
    out = []
    if todo:
        out.append(f"### Bài còn trống — {len(todo)} mục")
        for r in todo:
            out.append(f'- [ ] Ngày {r.get("day")}: **{r.get("keyword")}** → `--generate --day {r.get("day")}`')
    if waiting:
        out.append(f"### Draft chờ duyệt — {len(waiting)} bài")
        for r in waiting:
            out.append(f'- [ ] **{r.get("keyword")}** → đọc, duyệt rồi `--wp-push`')
    if not out:
        return VA_SECTION_BLANK
    return "\n".join(out)

def build_refresh_section(history: dict, drafts: dict, pushed: dict) -> str:
    from utils.keyword_groups import build_refresh_list
    from utils.refresh_diff import build_diff
    rows = build_diff(build_refresh_list(history or {}), drafts or {}, pushed or {})
    if not rows:
        return VA_SECTION_BLANK
    labels = {"chua_draft": "chưa viết", "cho_duyet": "chờ duyệt", "da_push": "đã push — theo dõi"}
    out = ["### Bài nên refresh"]
    for r in rows:
        box = "- [ ]" if r["state"] != "da_push" else "- [x]"
        out.append(f'{box} **{r["keyword"]}** (hạng {r["best_ever"]} → {r["current"]}) — {labels[r["state"]]}')
    return "\n".join(out)

def build_gap_section(pages: dict) -> str:
    from utils.content_gap import build_gaps
    rows = build_gaps(pages or {})
    if not rows:
        return VA_SECTION_BLANK
    out = ["### Google muốn, site chưa có trang riêng"]
    for r in rows:
        out.append(f'- [ ] "{r["query"]}" ({r["imps"]} imps đang đổ vào trang chủ) → lên bài riêng')
    return "\n".join(out)

def build_ctr_section(gsc_rows: dict) -> str:
    from utils.ctr_opportunities import build_opportunities
    rows = build_opportunities(gsc_rows or {})
    if not rows:
        return VA_SECTION_BLANK
    out = ["### Sửa title/meta (được thấy mà ít click)"]
    for r in rows[:10]:
        out.append(f'- [ ] "{r["query"]}" — vị trí {r.get("position", 0):,.1f}, '
                   f'CTR {r.get("ctr_pct", 0)}% vs bình quân {r.get("avg_pct", 0)}%')
    return "\n".join(out)

def build_backlink_section(links: list, state: dict) -> str:
    if not links:
        return VA_SECTION_BLANK
    out = ["### Backlink đã đặt — trạng thái check gần nhất"]
    n_check = 0
    for link in links:
        url = str((link or {}).get("url") or "")
        if not url:
            continue
        entry = (state or {}).get(url) or {}
        status = entry.get("status")
        alive = isinstance(status, int) and 200 <= status < 400
        label = ("còn sống" if alive else
                 (f"HTTP {status}" if isinstance(status, int) else "chưa check"))
        n_check += 1
        box = "- [x]" if alive else "- [ ]"
        out.append(f'{box} "{url}" — {label}')
    return "\n".join(out) if n_check else VA_SECTION_BLANK

def build_pack(sections: dict) -> str:
    day = date.today().isoformat()
    out = [f"# GÓI VIỆC NGÀY CHO VA — {day}",
           "",
           "Sinh tự động, chỉ tổng hợp dữ liệu có sẵn. VA thực hiện xong việc",
           "đánh dấu `[x]`; câu được hỏi dưới trả lời ở mục cuối khi báo lại owner.",
           "",
           "---", ""]
    order = ["plan", "refresh", "gap", "ctr", "backlink"]
    titles = {"plan": "Việc nội dung", "refresh": "Refresh",
              "gap": "Lỗ hổng nội dung", "ctr": "CTR cơ hội",
              "backlink": "Backlink"}
    for k in order:
        if k in sections:
            out += _section(titles[k], sections[k])
    return "\n".join(out).rstrip() + "\n"

def save_pack(text: str, when: str = None, base_dir: str = None) -> str:
    directory = base_dir or _site_data_dir()
    os.makedirs(directory, exist_ok=True)
    day = when or date.today().isoformat()
    path = os.path.join(directory, f"va_pack_{day}.md")
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
    return path

def _site_data_dir() -> str:
    from utils.site_paths import _site_data_dir as _d
    return _d()

def run_va_pack_cli() -> int:
    """`--va-pack`: gói việc cho VA → data/<slug>/va_pack_<ngày>.md."""
    import config.settings as cfg
    from utils.alerts import _log

    sections = {}
    def _put(name, fn):
        try:
            sections[name] = fn()
        except Exception as e:
            _log(f"[VA] mục {name} bỏ qua: {type(e).__name__}: {e}")
            sections[name] = VA_SECTION_BLANK

    def _plan():
        from utils.plan_progress import build_progress
        return build_plan_section(build_progress())

    def _refresh():
        from utils.keyword_groups import build_refresh_list
        from utils.refresh_diff import build_diff
        from utils.rank_tracker import _load_history
        from utils.plan_progress import scan_drafts, load_pushed
        return build_refresh_section(_load_history(), scan_drafts(), load_pushed())

    def _gap():
        from utils.gsc_pages import _snapshot_pages
        return build_gap_section(_snapshot_pages()[0])

    def _ctr():
        from utils.gsc_client import latest_gsc_rows
        return build_ctr_section(latest_gsc_rows())

    def _backlink():
        from utils.backlinks import load_links, load_state
        return build_backlink_section(load_links(), load_state())

    _put("plan", _plan)
    _put("refresh", _refresh)
    _put("gap", _gap)
    _put("ctr", _ctr)
    _put("backlink", _backlink)

    text = build_pack(sections)
    path = save_pack(text)
    print("=" * 104)
    print(f"  VA PACK — {date.today().isoformat()} | "
          f"{getattr(cfg, 'TARGET_URL', '') or '(chưa cấu hình site)'}")
    print("=" * 76)
    print(_note(text))
    print("=" * 104)
    print(f"  Đã ghi file hand-off: {path}")
    return 0
