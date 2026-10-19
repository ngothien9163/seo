# -*- coding: utf-8 -*-
"""utils/dispatch_tools.py — cầu nối GUI tab 🧰 Phân Tích: gọi lệnh CLI đọc-only.

GUI tab 🧰 có 8 nút; thay mỗi nút import module riêng (trùng cách CLI đã làm),
worker chung của GUI chỉ gọi dispatch_tools(tag) — một nơi duy nhất map tag →
lệnh thật. Chỉ các lệnh ĐỌC (0 request mới; doctor --net là exception, tự nuốt
lỗi mạng). KHÔNG có lệnh ghi state nào trong file này.
"""

def dispatch_tools(tag: str) -> int:
    """tag (klặn UI) → chạy CLI đúng; CLI tự in vào System Logs (stdout GUI)."""
    if tag == "page-impact":
        from utils.page_impact import run_page_impact_cli
        return run_page_impact_cli()
    if tag == "content-gap":
        from utils.content_gap import run_content_gap_cli
        return run_content_gap_cli()
    if tag == "refresh-diff":
        from utils.refresh_diff import run_refresh_diff_cli
        return run_refresh_diff_cli()
    if tag == "daily-report":
        from utils.daily_report import run_daily_cli
        return run_daily_cli()
    if tag == "post-report":
        from utils.post_report import run_post_report_cli
        return run_post_report_cli("")
    if tag == "outreach":
        from utils.outreach import run_list_cli
        return run_list_cli()
    raise ValueError(f"Unknown tool tag: {tag!r}")
