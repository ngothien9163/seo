"""
SEO2 — Chi?n l??c SEO toàn di?n cho topdev.vn

80% Content & Backlink | 20% Automation
"""
import sys

# Console Windows mặc định cp1252: in tiếng Việt là UnicodeEncodeError, chết giữa job
# khi Task Scheduler gọi mà không có ai nhìn. UTF-8 + replace = in không bao giờ nổ.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


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
    print("  python main.py --export rank|gsc|audit|backlinks|all  Xuat bao cao CSV mo bang Excel")
    print("  python main.py --alerts     Canh bao tut hang (Telegram/console, xem SETUP_ALERTS)")
    print("  python main.py --run-job rank|gsc|traffic  Goi 1 job (Windows Task Scheduler)")
    print("  python main.py --scheduler-status Xem job nao den gio chay, ket qua ra sao")
    print("  python main.py --audit [--audit-limit N]  Audit on-page site cua minh (HTML tinh)")
    print("  python main.py --pagespeed [URL]  Core Web Vitals tu PageSpeed Insights (so LAB)")
    print("  python main.py --export audit     Xuat ket qua audit lan gan nhat ra CSV")
    print("  python main.py --backlink-check   Verify backlink da dat: con song + co link toi site + dofollow")
    print('  python main.py --backlink-add "URL"  Them 1 backlink vao danh sach theo doi')
    print("  python main.py --backlink-import <file.csv>  Nap CSV 'External links' tai tu Search Console")
    print("  python main.py --backlink-refresh [--backlink-limit N]  Check lai het, bo qua cache 24h")
    print('  python main.py --generate "tu khoa"  Sinh bai bang Ollama (chi draft, khong tu dang)')
    print("  python main.py --generate --day 3    Lay muc ngay 3 trong content plan 30 ngay")
    print("  python main.py --generate \"kw\" --dry-run  Chi in prompt, khong goi Ollama")
    print("  python main.py --migrate-multi-site  Chep du lieu site hien tai vao data/<slug>/ (khong xoa goc)")
    print("  python main.py --migrate-multi-site --dry-run  Chi xem se copy gi, khong ghi")
    print("-" * 65)


def _flag_value(name: str) -> str:
    """Giá trị đứng ngay sau một flag ('--backlink-add URL').

    Flag kế tiếp ('' khi thiếu) hoặc token bắt đầu bằng '-' nghĩa là flag đó không
    có giá trị — gọi hàm CLI với chuỗi trống để nó tự in cách dùng, không đoán bừa.
    """
    if name not in sys.argv:
        return ""
    i = sys.argv.index(name)
    nxt = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""
    return nxt if nxt and not nxt.startswith("-") else ""


if __name__ == "__main__":
    if "--auto" in sys.argv or "--search" in sys.argv:
        # 20% Automation — 1 session, giới hạn phiên vẫn do utils/rate_limiter.py quyết
        from utils.automation import run_one_session
        use_search = "--search" in sys.argv or "--direct" not in sys.argv
        sys.exit(run_one_session(use_search))

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

    elif "--alerts" in sys.argv:
        from utils.alerts import run_alert_check_cli
        sys.exit(run_alert_check_cli())

    elif "--run-job" in sys.argv:
        from utils.scheduler import run_job
        i = sys.argv.index("--run-job")
        nxt = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""
        name = nxt if nxt and not nxt.startswith("-") else ""
        sys.exit(run_job(name))

    elif "--scheduler-status" in sys.argv:
        from utils.scheduler import run_status_cli
        sys.exit(run_status_cli())

    elif "--audit" in sys.argv or "--audit-limit" in sys.argv:
        from utils.site_auditor import run_audit_cli
        i = sys.argv.index("--audit-limit") if "--audit-limit" in sys.argv else -1
        limit = None
        if i >= 0:
            nxt = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""
            # để trống khi token kế tiếp là flag khác -> dùng AUDIT_MAX_PAGES, còn giá trị
            # sai ("abc", "-5") thì run_audit_cli tự báo và exit 2
            limit = nxt if nxt and not nxt.startswith("-") else None
        sys.exit(run_audit_cli(limit=limit))

    elif "--pagespeed" in sys.argv:
        from utils.pagespeed import run_pagespeed_cli
        i = sys.argv.index("--pagespeed")
        nxt = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""
        target = nxt if nxt and not nxt.startswith("-") else ""
        sys.exit(run_pagespeed_cli(target))

    elif "--backlink-check" in sys.argv or "--backlink-refresh" in sys.argv:
        from utils.backlink_checker import run_backlink_check_cli
        sys.exit(run_backlink_check_cli(limit=_flag_value("--backlink-limit") or None,
                                        refresh="--backlink-refresh" in sys.argv))

    elif "--backlink-add" in sys.argv:
        from utils.backlink_checker import run_backlink_add_cli
        sys.exit(run_backlink_add_cli(_flag_value("--backlink-add")))

    elif "--backlink-import" in sys.argv:
        from utils.backlink_checker import run_backlink_import_cli
        sys.exit(run_backlink_import_cli(_flag_value("--backlink-import")))

    elif "--generate" in sys.argv:
        from content.generator import run_generate_cli
        sys.exit(run_generate_cli(keyword=_flag_value("--generate"),
                                  day=_flag_value("--day"),
                                  dry_run="--dry-run" in sys.argv))

    elif "--migrate-multi-site" in sys.argv:
        from utils.migrate_sites import run_migrate_cli
        sys.exit(run_migrate_cli(dry_run="--dry-run" in sys.argv))

    else:
        show_strategy()
