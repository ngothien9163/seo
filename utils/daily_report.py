# -*- coding: utf-8 -*-
"""utils/daily_report.py — F10d: `--daily-report` — báo cáo BUỔI SÁNG gộp 1 tin/ngày.

Khác `--weekly` (báo cáo TUẦN đầy đủ, 1 lần/tuần): báo cáo này nhẹ, dựng là gộp
ba thứ một người quản nhiều site cần mỗi sáng:
1. **Xếp hạng** — tóm tắt hạng hiện tại (tail từ rank_tracker.build_report());
2. **Search Console** — tóm tắt GSC (tail từ gsc_client.build_report());
3. **Việc hôm nay** — top N mục còn trống của content plan 30 ngày (plan_progress),
   + đếm draft chờ duyệt (has_draft mà chưa push), + nhắc backlink cần check khi
   cấu hình mà lâu không verify.

KHÔNG đánh dấu ngày trong state (khác weekly): chạy 2 lần trong 1 ngày là in 2
tin — chi phí thấp, người dùng tự chọn giờ chạy (scheduler SCHEDULER_REPORT_HOURS
hoặc tay). Ghi file markdown tùy chọn `--daily-report --save` → data/<slug>/daily_<ngày>.md
để mở lại lúc nào cũng được (atomic như mọi state).

Mọi builder nhận tham số để test thuần; nguồn trống/hỏng → bỏ phần đó, không
làm báo cáo chết (cùng nguyên tắc weekly_digest).
"""
import os
from datetime import date

import utils.site_paths as sp

TELEGRAM_MAX = 4096          # cắt đúng biên Telegram (cùng weekly)
TAIL_SECTION = 10            # mỗi phần nguồn tối đa N dòng cuối (ít hơn weekly: tin hàng ngày)
TOP_TODO = 5                 # "Việc hôm nay" liệt kê tối đa N mục trống


def _tail(text: str, tail: int = TAIL_SECTION) -> list[str]:
    """N dòng cuối CÓ NỘI DUNG (bỏ dòng trang trí '='/'─' trống — cùng weekly _section)."""
    if not text or not str(text).strip():
        return []
    content = [ln.rstrip() for ln in str(text).strip().splitlines()
               if ln.strip() and not set(ln.strip()) <= {"=", "─", "-"}]
    return content[-tail:]


def build_todo_lines(plan_rows: list, n_backlinks: int = -1) -> list[str]:
    """[dòng] của phần "Việc hôm nay" — thuần, không đọc file (caller cung cấp)."""
    lines = []
    todo = [r for r in (plan_rows or []) if not r.get("pushed") and not r.get("has_draft")]
    waiting = [r for r in (plan_rows or []) if r.get("has_draft") and not r.get("pushed")]
    if todo:
        lines.append(f"- Content plan còn {len(todo)} mục chưa làm — 5 mục kế:")
        for r in todo[:TOP_TODO]:
            lines.append(f'    · ngày {r.get("day")}: {r.get("keyword")}'
                         " (làm draft: --generate --day N)")
        lines.append("  Xem đủ 30 mục: --plan-progress")
    if waiting:
        lines.append(f"- {len(waiting)} draft CHỜ DUYỆT chưa push WP (xem: --plan-progress, đẩy: --wp-push)")
    if n_backlinks == 0:
        lines.append("- Backlink: chưa có link nào trong danh sách — đặt link đầu rồi --backlink-add")
    return lines


def build_report(rank_text: str = None, gsc_text: str = None,
                 plan_rows: list = None, n_backlinks: int = -1) -> str:
    """Báo cáo gộp hàng ngày. Nguồn trống/hỏng → phần đó tự nói "chưa có dữ liệu"."""
    from datetime import datetime as _dt

    lines = [f"BÁO CÁO NGÀY — {date.today().isoformat()}",
             f"Site: {sp.site_domain() or '(chưa cấu hình)'}"]
    for title, text in (("── XẾP HẠNG ──", rank_text), ("── SEARCH CONSOLE ──", gsc_text)):
        tail = _tail(text)
        if tail:
            lines.append("")
            lines.append(title)
            lines.extend(tail)

    todo = build_todo_lines(plan_rows, n_backlinks)
    if todo:
        lines.append("")
        lines.append("── VIỆC HÔM NAY ──")
        lines.extend(todo)
    if len(lines) <= 2:
        lines.append("")
        lines.append("Chưa có dữ liệu — chạy --rank / --gsc trước (source nào cũng tự nói thiếu gì).")
    return "\n".join(lines)


def _clip(text: str, limit: int = TELEGRAM_MAX) -> str:
    """Cắt đúng limit, gãy ở biên dòng, đuôi ghi rõ bị cắt (cùng weekly)."""
    if len(text) <= limit:
        return text
    head = text[:limit - 40].rsplit("\n", 1)[0]
    return head + "\n… (bị cắt — chi tiết: --rank-report / --gsc-report)"


def save_report(text: str, when: str = None, base_dir: str = None) -> str:
    """Ghi `daily_<ngày>.md` vào data/<slug>/ — atomic, trả đường dẫn. Thuần qua base_dir khi test."""
    directory = base_dir or sp._site_data_dir()
    os.makedirs(directory, exist_ok=True)
    day = when or date.today().isoformat()
    path = os.path.join(directory, f"daily_{day}.md")
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
    return path


def run_daily_cli(save_to_disk: bool = False) -> int:
    """Entry `--daily-report`: dựng báo cáo, gửi qua kênh alerts, tùy chọn lưu file."""
    from utils.alerts import send, delivery_mode, _log

    # mỗi nguồn subset báo lỗi riêng — hỏng nguồn nào nguồn đó bị bỏ, không chết cả tin
    rank_text = gsc_text = ""
    plan_rows = []
    n_backlinks = -1
    try:
        from utils.rank_tracker import build_report as rank_report
        rank_text = rank_report() or ""
    except Exception as e:
        _log(f"[Daily] phần xếp hạng bỏ qua: {type(e).__name__}: {e}")
    try:
        from utils.gsc_client import build_report as gsc_report
        gsc_text = gsc_report() or ""
    except Exception as e:
        _log(f"[Daily] phần GSC bỏ qua: {type(e).__name__}: {e}")
    try:
        from utils.plan_progress import build_progress
        plan_rows = build_progress()
    except Exception as e:
        _log(f"[Daily] phần plan bỏ qua: {type(e).__name__}: {e}")
    try:
        import json
        from utils.site_paths import site_file
        p = site_file("backlinks.json")
        if os.path.exists(p):
            n_backlinks = len(json.load(open(p, encoding="utf-8")).get("backlinks", []))
    except Exception:
        pass

    text = _clip(build_report(rank_text, gsc_text, plan_rows, n_backlinks))
    ok = send(text)
    mode = delivery_mode()
    if ok:
        _log(f"Báo cáo ngày {date.today().isoformat()} đã qua kênh {mode}.")
        if save_to_disk:
            path = save_report(text)
            _log(f"Đã lưu để xem lại: {path}")
        return 0
    _log("Chưa gửi được — thử lại lần chạy sau (không đánh dấu gì, không mất tin).")
    return 1
