"""
SEO2 — Chi?n l??c SEO toàn di?n cho topdev.vn

80% Content & Backlink | 20% Automation
"""
import sys

def show_strategy():
    """Hi?n th? chi?n l??c t?ng th?."""
    from content.planner import print_plan, get_plan_summary
    from content.keyword_research import print_keyword_report
    from backlinks.tracker import print_backlink_plan

    print("=" * 65)
    print("  SEO2 - CHIEN LUOC TOAN DIEN CHO TOPDEV.VN")
    print("  80% Content & Backlink | 20% Automation")
    print("=" * 65)

    # Content Strategy
    print_plan()
    print()

    # Keyword Research
    try:
        print_keyword_report()
    except Exception as e:
        print(f"Keyword report error: {e}")
    print()

    # Backlink Strategy
    try:
        print_backlink_plan()
    except Exception as e:
        print(f"Backlink plan error: {e}")
    print()

    # Automation notice
    print("-" * 65)
    print("  AUTOMATION (20%) - Chay khi can")
    print("  " + "=" * 61)
    print("  python main.py --search    Gioi han 25 session/ngay, mobile 70%")
    print("  python main.py --direct    Truy cap truc tiep (khong qua Google)")
    print("  python main.py --plan      Xem content plan 30 ngay")
    print("  python main.py --keywords  Xem keyword research")
    print("  python main.py --backlinks Xem backlink strategy")
    print("  python main.py --rank       Kiem tra vi tri tu khoa tren Google")
    print("  python main.py --rank-report Xem bao cao xep hang da luu")
    print("  python main.py --gsc        Lay du lieu Search Console (clicks/impressions)")
    print("  python main.py --gsc-report Xem bao cao Search Console da luu")
    print('  python main.py --gsc-keywords      Tu keyword de xuat tu query cua Search Console')
    print('  python main.py --gsc-add-keyword "..."  Them 1 tu keyword vao theo doi (--yes: khong hoi)')
    print("  python main.py --export rank|gsc|all  Xuat bao cao CSV mo bang Excel")
    print("-" * 65)


if __name__ == "__main__":
    if "--auto" in sys.argv or "--search" in sys.argv:
        # 20% Automation — gi?i h?n 25 session/ngày
        from utils.rate_limiter import can_run_session, mark_session_run, get_today_summary
        import asyncio

        summary = get_today_summary()
        print(f"[RateLimit] H�m nay ch?y: {summary['ran']}/{summary['ran'] + summary['remaining']} session")

        allowed, reason = can_run_session()
        if not allowed:
            print(f"[RateLimit] {reason}")
            sys.exit(1)

        # M?c d?nh dùng search flow (traffic t? Google) — t? nhi�n h?n direct
        use_search = "--search" in sys.argv or not "--direct" in sys.argv
        mode = "SEARCH (Google)" if use_search else "DIRECT"
        print(f"Ch?y automation mode — Traffic: {mode} (gi?i h?n 25 session/ngày)")

        from core.browser_manager import BrowserManager

        async def run_limited():
            mgr = BrowserManager()
            browser = await mgr.launch_browser()
            page = await mgr.create_context(browser)

            if use_search:
                from tests.test_search_flow import run_search_flow
                await run_search_flow(page)
            else:
                from tests.test_direct_access import run_deep_session
                await run_deep_session(page)

            await mgr.close()

        asyncio.run(run_limited())
        mark_session_run()
        print(f"[RateLimit] D? xong. Còn {get_today_summary()['remaining']} session h�m nay.")

    elif "--plan" in sys.argv:
        from content.planner import print_plan
        print_plan()

    elif "--keywords" in sys.argv:
        from content.keyword_research import print_keyword_report
        print_keyword_report()

    elif "--backlinks" in sys.argv:
        from backlinks.tracker import print_backlink_plan
        print_backlink_plan()

    elif "--rank" in sys.argv:
        import asyncio
        from utils.rank_tracker import run_rank_check_cli
        asyncio.run(run_rank_check_cli())

    elif "--rank-report" in sys.argv:
        from utils.rank_tracker import print_report
        print_report()

    elif "--gsc" in sys.argv:
        from utils.gsc_client import run_gsc_fetch_cli
        run_gsc_fetch_cli()

    elif "--gsc-report" in sys.argv:
        from utils.gsc_client import print_report
        print_report()

    elif "--gsc-keywords" in sys.argv:
        from utils.gsc_client import run_keyword_suggest_cli
        sys.exit(run_keyword_suggest_cli())

    elif "--gsc-add-keyword" in sys.argv:
        from utils.gsc_client import run_add_keyword_cli
        i = sys.argv.index("--gsc-add-keyword")
        nxt = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""
        kw = nxt if nxt and not nxt.startswith("-") else ""
        sys.exit(run_add_keyword_cli(kw, assume_yes="--yes" in sys.argv))

    elif "--export" in sys.argv:
        from utils.exporter import run_export_cli
        i = sys.argv.index("--export")
        nxt = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""
        kind = nxt if nxt and not nxt.startswith("-") else "all"
        sys.exit(run_export_cli(kind))

    else:
        show_strategy()
