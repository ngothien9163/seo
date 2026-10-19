"""
SEO2 — Chiến lược SEO toàn diện cho topdev.vn

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
    """Hiển thị chiến lược tổng thể."""
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
    print("  python main.py --gsc-pages  Cannibalization theo Google that: query nao do may trang phuc vu")
    print("  python main.py --page-impact  Suc nang theo trang: trang VIP, trang phoi khong ai click (tu GSC)")
    print("  python main.py --content-gap  Query Google phoi ma site chua co trang rieng (tu GSC)")
    print("  python main.py --refresh-diff  Bai nen refresh da den buoc nao: chua draft / cho duyet / da push")
    print("  python main.py --va-pack       Goi viec ngay cho VA — 1 file md checklist (data/<slug>/va_pack_<ngay>.md)")
    print('  python main.py --yoast-meta ID  Patch Yoast focuskw/meta cho bai draft/pending tren WP')
    print('  python main.py --content-brief "kw" [-save]  Brief tron du lieu cho 1 tu khoa (khong goi Ollama)')
    print("  python main.py --gsc-trend   Xu huong imps/clicks/CTR theo query, 8 moc gan nhat")
    print("  python main.py --gsc-alerts  Canh bao imps rut manh giua 2 snapshot GSC (ve --gsc truoc)")
    print('  python main.py --gsc-keywords      Tu keyword de xuat tu query cua Search Console')
    print('  python main.py --gsc-add-keyword "..."  Them 1 tu keyword vao theo doi (--yes: khong hoi)')
    print("  python main.py --export rank|gsc|audit|backlinks|plan|all  Xuat bao cao CSV mo bang Excel")
    print("  python main.py --alerts     Canh bao tut hang (Telegram/console, xem SETUP_ALERTS)")
    print("  python main.py --weekly     Bao cao tuan gop SERP+GSC+AEO -> Telegram (1 lan/tuan)")
    print("  python main.py --daily-report [-save]  Bao cao buoi sang 1 tin: rank tail + GSC tail + viec hom nay")
    print("  python main.py --run-job rank|gsc|traffic  Goi 1 job (Windows Task Scheduler)")
    print("  python main.py --scheduler-status Xem job nao den gio chay, ket qua ra sao")
    print("  python main.py --audit [--audit-limit N]  Audit on-page site cua minh (HTML tinh)")
    print("  python main.py --pagespeed [URL]  Core Web Vitals tu PageSpeed Insights (so LAB)")
    print("  python main.py --export audit     Xuat ket qua audit lan gan nhat ra CSV")
    print("  python main.py --audit-actions    Bien finding audit thanh viec uu tien theo tu khoa")
    print("  python main.py --audit-diff       Loi moi phat hien vs da sua giua 2 lan audit gan nhat")
    print("  python main.py --plan-progress    Muc nao cua plan 30 ngay da co draft / da push WP")
    print('  python main.py --wp-push <file.md> [--status draft]  Day 1 ban nhap .md len WordPress (CHI draft/pending)')
    print("  python main.py --doctor [--net]  Kiem tra moi truong: GSC/Telegram/Ollama/WP/keywords (khong mang tru --net)")
    print("  python main.py --internal-links  Goi y link noi bo tu du lieu audit + rank hien co")
    print("  python main.py --competitors     Domain doi thu xuat hien nhieu nhat tren SERP (tu rank history)")
    print("  python main.py --keyword-groups  Cum tu khoa + danh sach bai nen refresh (tu du lieu co san)")
    print("  python main.py --cluster-gsc  Cum tu khoa theo du lieu Google that (imps/clicks GSC, cum mù GSC)")
    print("  python main.py --rank-urls       Trang nao dang rank cho tu nao + canh bao doi trang")
    print("  python main.py --ctr-ops         Query duoc thay ma it nguoi click - goi y sua title/meta (tu GSC)")
    print('  python main.py --aeo-questions "kw"  Bien the cau hoi AEO de dan tay vao AI engine')
    print("  python main.py --html-report     Xuat 1 file report.html (SERP+GSC+Audit+Backlink), mo bang browser")
    print("  python main.py --backlink-check   Verify backlink da dat: con song + co link toi site + dofollow")
    print('  python main.py --backlink-add "URL"  Them 1 backlink vao danh sach theo doi')
    print("  python main.py --backlink-import <file.csv>  Nap CSV 'External links' tai tu Search Console")
    print("  python main.py --backlink-refresh [--backlink-limit N]  Check lai het, bo qua cache 24h")
    print('  python main.py --generate "tu khoa"  Sinh bai bang Ollama (chi draft, khong tu dang)')
    print("  python main.py --generate --day 3    Lay muc ngay 3 trong content plan 30 ngay")
    print("  python main.py --generate \"kw\" --dry-run  Chi in prompt, khong goi Ollama")
    print("  python main.py --migrate-multi-site  Chep du lieu site hien tai vao data/<slug>/ (khong xoa goc)")
    print("  python main.py --migrate-multi-site --dry-run  Chi xem se copy gi, khong ghi")
    print("  python main.py --site domain.com --rank  Chay lenh cho MOTE site khac (da migrate) trong cung project")
    print("  python main.py --sites    Xem so site (config/sites.json) + site nao du lieu da tach rieng")
    print('  python main.py --site-add "https://web.com"    Them site vao so (site nen da migrate truoc)')
    print('  python main.py --site-remove "https://web.com" Bo site khoi so (khong xoa du lieu)')
    print('  python main.py --sites-run "--rank"  Chay 1 lenh qua TUNG site trong so (process con moi site)')
    print("  python main.py --aeo-report           AI engine co nhac brand khong (du lieu da paste)")
    print('  python main.py --aeo-check file.txt --aeo-keyword "kw" [--aeo-engine ChatGPT]  Luu 1 cau tra loi')
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
    if "--site" in sys.argv:
        # Chọn site cho cả phiên — phải áp TRƯỚC khi branch nào import module state,
        # vì default path tính lúc import. Module cũng re-resolve lúc gọi nên an toàn 2 lớp.
        import config.settings as cfg
        from utils import site_paths
        _sel = _flag_value("--site")
        if _sel:
            cfg.TARGET_URL = _sel if "://" in _sel else f"https://{_sel}"
            _dom = site_paths.site_domain()
            if _dom:
                cfg.GSC_SITE_URL = f"sc-domain:{_dom}"
            print(f"[Site] Site đang làm việc: {_dom}  (nhà dữ liệu: data/{site_paths.site_slug()}/)")
            if not site_paths.is_multi_site():
                # Chưa migrate = mọi thứ vẫn đọc/ghi file phẳng ở gốc project, tức là
                # dữ liệu của site KHÁC (hoặc của chính site cũ). Nói thẳng ra thay vì để
                # owner tưởng đang xem số liệu riêng của site vừa chọn.
                print(f"[Site] ⚠️  Site chưa migrate: dữ liệu vẫn ở file phẳng gốc project, "
                      f"KHÔNG phải dữ liệu riêng của {_dom}.")
                print(f"[Site]     Tách riêng ngay: python main.py --site {_dom} --migrate-multi-site")
        else:
            print("[Site] --site cần domain/URL, ví dụ: --site shoplanhdep.com")

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

    elif "--gsc-pages" in sys.argv:
        from utils.gsc_pages import run_gsc_pages_cli
        sys.exit(run_gsc_pages_cli())

    elif "--page-impact" in sys.argv:
        from utils.page_impact import run_page_impact_cli
        sys.exit(run_page_impact_cli())

    elif "--content-gap" in sys.argv:
        from utils.content_gap import run_content_gap_cli
        sys.exit(run_content_gap_cli())

    elif "--refresh-diff" in sys.argv:
        from utils.refresh_diff import run_refresh_diff_cli
        sys.exit(run_refresh_diff_cli())

    elif "--va-pack" in sys.argv:
        from utils.va_pack import run_va_pack_cli
        sys.exit(run_va_pack_cli())

    elif "--yoast-meta" in sys.argv:
        from utils.wp_yoast import run_yoast_cli
        sys.exit(run_yoast_cli(post_id=_flag_value("--yoast-meta"),
                               keyword=_flag_value("--kw")))

    elif "--content-brief" in sys.argv:
        from utils.content_brief import run_content_brief_cli
        sys.exit(run_content_brief_cli(keyword=_flag_value("--content-brief"),
                                       save_to_disk="--save" in sys.argv))

    elif "--gsc-trend" in sys.argv:
        from utils.gsc_trend import run_gsc_trend_cli
        sys.exit(run_gsc_trend_cli())

    elif "--gsc-alerts" in sys.argv:
        from utils.gsc_alerts import run_gsc_alerts_cli
        sys.exit(run_gsc_alerts_cli())

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

    elif "--audit-actions" in sys.argv:
        from utils.audit_actions import run_audit_actions_cli
        sys.exit(run_audit_actions_cli())

    elif "--audit-diff" in sys.argv:
        from utils.audit_diff import run_audit_diff_cli
        sys.exit(run_audit_diff_cli())

    elif "--plan-progress" in sys.argv:
        from utils.plan_progress import run_plan_progress_cli
        sys.exit(run_plan_progress_cli())

    elif "--wp-push" in sys.argv:
        from utils.wp_publisher import run_push_cli
        i = sys.argv.index("--wp-push")
        nxt = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""
        path = nxt if nxt and not nxt.startswith("-") else ""
        status = "pending" if "--status" in sys.argv and "pending" in sys.argv else "draft"
        title = _flag_value("--title")
        excerpt = _flag_value("--excerpt")
        sys.exit(run_push_cli(path, status=status, title=title, excerpt=excerpt))

    elif "--doctor" in sys.argv:
        from utils.doctor import run_doctor_cli
        sys.exit(run_doctor_cli(net="--net" in sys.argv))

    elif "--html-report" in sys.argv:
        from utils.html_report import run_html_report_cli
        # đường dẫn tùy chọn ngay sau cờ; bỏ trống → data/report.html (per-site)
        sys.exit(run_html_report_cli(_flag_value("--html-report")))

    elif "--internal-links" in sys.argv:
        from utils.internal_links import run_internal_links_cli
        sys.exit(run_internal_links_cli())

    elif "--competitors" in sys.argv:
        from utils.competitors import run_competitors_cli
        sys.exit(run_competitors_cli())

    elif "--keyword-groups" in sys.argv:
        from utils.keyword_groups import run_keyword_groups_cli
        sys.exit(run_keyword_groups_cli())

    elif "--cluster-gsc" in sys.argv:
        from utils.cluster_gsc import run_cluster_gsc_cli
        sys.exit(run_cluster_gsc_cli())

    elif "--rank-urls" in sys.argv:
        from utils.rank_urls import run_rank_urls_cli
        sys.exit(run_rank_urls_cli())

    elif "--ctr-ops" in sys.argv:
        from utils.ctr_opportunities import run_ctr_cli
        sys.exit(run_ctr_cli())

    elif "--aeo-questions" in sys.argv:
        from utils.aeo_prompts import run_aeo_questions_cli
        sys.exit(run_aeo_questions_cli())

    elif "--weekly" in sys.argv:
        from utils.weekly_digest import run_weekly_cli
        sys.exit(run_weekly_cli(force="--force" in sys.argv))

    elif "--daily-report" in sys.argv:
        from utils.daily_report import run_daily_cli
        sys.exit(run_daily_cli(save_to_disk="--save" in sys.argv))

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

    elif "--sites" in sys.argv:
        from utils.site_registry import run_sites_cli
        sys.exit(run_sites_cli())

    elif "--site-add" in sys.argv:
        from utils.site_registry import run_site_add_cli
        sys.exit(run_site_add_cli(_flag_value("--site-add"),
                                  label=_flag_value("--label")))

    elif "--site-remove" in sys.argv:
        from utils.site_registry import run_site_remove_cli
        sys.exit(run_site_remove_cli(_flag_value("--site-remove")))

    elif "--sites-run" in sys.argv:
        # F10c — chạy 1 lệnh qua TỪNG site trong sổ (process con mỗi site):
        # args sau --sites-run, vd: --sites-run "--rank"  /  --sites-run "--rank --gsc"
        from utils.sites_run import run_sites_run_cli
        _i = sys.argv.index("--sites-run")
        _rest = sys.argv[_i + 1:]
        sys.exit(run_sites_run_cli(_rest))

    elif "--aeo-check" in sys.argv or "--aeo-report" in sys.argv:
        # F9 — phân tích câu trả lời AI dán tay; không gửi request nào ra ngoài
        if "--aeo-report" in sys.argv:
            from utils.aeo import run_aeo_report_cli
            sys.exit(run_aeo_report_cli())
        from utils.aeo import run_aeo_check_cli
        # --aeo-engine chỉ là tên dán nhãn — engine tự do, không hạn chế danh sách
        sys.exit(run_aeo_check_cli(_flag_value("--aeo-check"),
                                   engine=_flag_value("--aeo-engine") or "ChatGPT",
                                   keyword=_flag_value("--aeo-keyword")))

    else:
        show_strategy()
