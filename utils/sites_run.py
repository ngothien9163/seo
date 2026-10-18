# -*- coding: utf-8 -*-
"""utils/sites_run.py — F10c: `--sites-run "<lệnh>"` — chạy 1 lệnh qua TỪNG site trong sổ.

Kiến trúc F10 chốt: MỘT PHIÊN = MỘT SITE (module state resolve 1 lần lúc import +
re-resolve lúc gọi nhưng cố tính không "nhảy site giữa phiên"). Vậy for-loop bên
trong cùng process là CHẠM PHÁP — mỗi con chó một process con:
    python main.py --site <url> <các-arg>
In băng thông correct cho việc: exit code của mỗi site được lookahead tổng hợp —
site nào lỗi CŨNG CHẠY HẾT SỔ (site chết không cản site khác), rồi cả tổng báo cáo.

Chỉ stdlib. Không network trực tiếp (con là main.py làm việc thật); KHÔNG tự
dùng --auto/--search/--migrate trong các lệnh (cụm) — các lệnh sẽ bị loại từ chối.
"""
import subprocess
import sys

import utils.site_paths as sp
from utils.site_registry import load, domain_of

FORBIDDEN = ("--site", "--site-add", "--site-remove", "--sites-run",
             "--migrate-multi-site", "--auto", "--search", "--direct", "--help")

TIMEOUT_PER_SITE = 30 * 60   # 30 phút cho 1 site — đủ cho --rank đầy đủ, chặn treo vĩnh viễn


def build_child_argv(url: str, args: list) -> list:
    """[sys.executable, main.py, --site, url, *args] — con đọc cùng codebase."""
    return [sys.executable, "main.py", "--site", url, *args]


def run_over_sites(urls: list, args: list) -> int:
    """Chạy tuần tự 1 process con mỗi site; in tiêu đề mỗi site; trả tổng exit code
    (số site lỗi — 0 = cả sổ xanh). args rỗng → không hợp lệ, caller tự kiểm."""
    if not args:
        print("[SitesRun] Chưa nói chạy lệnh gì — dùng: python main.py --sites-run \"--rank\"")
        print('[SitesRun]         hoặc nhiều lệnh: python main.py --sites-run "--rank --gsc"')
        return 2
    bad = [a for a in args if a in FORBIDDEN]
    if bad:
        print(f"[SitesRun] {', '.join(bad)} là lệnh quản sổ/phiên — không được chạy through "
              "--sites-run (loop sẽ tự lặp nó vô hạn).")
        return 2

    if not urls:
        print("[SitesRun] Sổ site trống — thêm site trước: python main.py --sites")
        return 2

    print("=" * 78)
    print(f"  SITES-RUN: {' '.join(args)} — {len(urls)} site")
    print("=" * 78)

    results = []
    for i, url in enumerate(urls, 1):
        dom = domain_of(url) or url
        slug = sp.slugify_domain(dom)
        migrated = slug in set(sp.known_site_slugs())
        print()
        print(f"── [{i}/{len(urls)}] {dom}"
              + ("" if migrated else "  ⚠️ CHƯA migrate — con sẽ chạy nhưng dữ liệu nền chung flat-file"))
        argv = build_child_argv(url, args)
        try:
            proc = subprocess.run(argv, timeout=TIMEOUT_PER_SITE)
            code = proc.returncode
        except subprocess.TimeoutExpired:
            print(f"[SitesRun] ⏰ {dom} quá {TIMEOUT_PER_SITE // 60} phút — bỏ qua site này, chạy site kế.")
            code = 124
        results.append({"url": dom, "code": code})

    print()
    print("=" * 78)
    print("  TỔNG SITES-RUN")
    print("=" * 78)
    for r in results:
        mark = "✅" if r["code"] == 0 else f"❌ exit={r['code']}"
        print(f'  {mark:<18}{r["url"]}')
    failures = sum(1 for r in results if r["code"] != 0)
    print(f"  {len(results) - failures}/{len(results)} site OK"
          + (f" — {failures} site lỗi (đã chạy hết sổ, site chết không cản site khác)."
             if failures else " — cả sổ xanh."))
    return failures


def run_sites_run_cli(args: list) -> int:
    """Entry `--sites-run`: đọc sổ sites.json rồi chạy args qua từng site."""
    urls = [r["url"] for r in load()]
    return run_over_sites(urls, list(args or []))
