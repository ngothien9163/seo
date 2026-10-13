"""
utils/automation.py — chạy ĐÚNG MỘT session traffic, dùng chung cho CLI và lịch.

Đây là flow cũ nằm inline trong `main.py --auto`, tách ra để:
1. `main.py --auto` / `--search` và scheduler (F4) gọi cùng một hàm — không hai bản copy;
2. giới hạn phiên vẫn do utils/rate_limiter.py quyết định: `can_run_session()` trước khi
   mở browser, `mark_session_run()` chỉ khi session chạy xong (lỗi giữa chừng thì không đếm).

Trả về exit code int (0 = xong, 1 = bị chặn hoặc nổ) — không bao giờ raise, không sys.exit.
"""
import asyncio

from utils.rate_limiter import can_run_session, get_today_summary, mark_session_run


def _one_session(use_search: bool) -> None:
    async def run():
        from core.browser_manager import BrowserManager
        mgr = BrowserManager()
        try:
            browser = await mgr.launch_browser()
            page = await mgr.create_context(browser)
            if use_search:
                from tests.test_search_flow import run_search_flow
                await run_search_flow(page)
            else:
                from tests.test_direct_access import run_deep_session
                await run_deep_session(page)
        finally:
            # phải đóng kể cả khi flow nổ, nếu không tiến trình chromium treo lại
            await mgr.close()

    asyncio.run(run())


def run_one_session(use_search: bool = True) -> int:
    summary = get_today_summary()
    print(f"[RateLimit] Hôm nay chạy: {summary['ran']}/{summary['ran'] + summary['remaining']} session")

    allowed, reason = can_run_session()
    if not allowed:
        print(f"[RateLimit] {reason}")
        return 1

    mode = "SEARCH (Google)" if use_search else "DIRECT"
    print(f"[RateLimit] Chạy automation mode — Traffic: {mode}")

    try:
        _one_session(use_search)
    except SystemExit as e:
        print(f"[RateLimit] Session bị dừng bởi sys.exit({e.code}) — không tính là đã chạy.")
        return 1
    except BaseException as e:
        print(f"[RateLimit] Session lỗi: {type(e).__name__}: {str(e)[:150]} — không tính là đã chạy.")
        return 1

    mark_session_run()
    print(f"[RateLimit] Xong. Còn {get_today_summary()['remaining']} session hôm nay.")
    return 0
