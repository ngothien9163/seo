"""
utils/rank_tracker.py — Theo dõi vị trí từ khóa trên Google (Rank Tracker).

Luồng:
1. Search từng từ khóa trong load_keywords() (config/keywords.json) trên Google (num=100, hl=vi, pws=0)
2. Tìm vị trí của domain mục tiêu trong kết quả organic
3. Lưu lịch sử vào rank_history.json (tồn tại qua các lần restart)
4. Giới hạn an toàn: tối đa RANK_CHECK_MAX_PER_DAY lần check/ngày + cooldown

Chạy:
    python main.py --rank          # Check + in báo cáo
    python main.py --rank-report   # Chỉ xem báo cáo lịch sử
    GUI: tab "📈 Xếp Hạng"

Ghi chú an toàn:
- Profile browser riêng "rank_tracker" được tái sử dụng giữa các lần check
  để Google thấy trình duyệt "quen thuộc", giảm CAPTCHA.
- Thứ tự từ khóa được xáo trộn mỗi lần check để tránh pattern lặp.
- Gặp CAPTCHA → dừng ngay, lưu kết quả một phần đã check được.
"""
import asyncio
import json
import os
import random
import time
from datetime import datetime, date
from urllib.parse import quote, urlparse

from playwright.async_api import Page

import config.settings as cfg
from utils import alerts
from utils.keywords import load_keywords
from utils.interactions import random_sleep, human_scroll
from tests.test_search_flow import (
    _accept_google_consent,
    _is_captcha,
    _unwrap_google_redirect,
)

import utils.site_paths as _site_paths

_HISTORY_NAME = "rank_history.json"
_DEFAULT_HISTORY_PATH = _site_paths.site_file(_HISTORY_NAME)
# Slot override cho test/CLI; mọi code đọc qua _history_path() chứ không dùng thẳng biến này.
HISTORY_FILE = _DEFAULT_HISTORY_PATH


def _history_path() -> str:
    """Đường dẫn rank history lúc gọi. Test gán HISTORY_FILE → tôn trọng; không → resolve per-site."""
    if HISTORY_FILE != _DEFAULT_HISTORY_PATH:
        return HISTORY_FILE
    return _site_paths.site_file(_HISTORY_NAME)

# Selector chứa kết quả organic của Google (thử lần lượt, selector đầu tiên có kết quả được dùng)
_SERP_SELECTORS = ["#search a[href]", "#rso a[href]", "#main a[href]"]

# Domain thuộc Google/ads — loại khỏi danh sách organic
_SKIP_NETLOC = ("google.", "googleusercontent.", "gstatic.", "googleadservices.", "doubleclick.")

MAX_CHECKS_KEPT = 90  # Số lần check lưu lại tối đa trong lịch sử


# ─── LỊCH SỬ: đọc / ghi ──────────────────────────────────────────────────────

def _load_history() -> dict:
    path = _history_path()
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"domain": "", "checks": {}, "state": {"date": "", "count": 0, "last_check": 0}}


def _save_history(data: dict):
    """Ghi nguyên tử (tmp + os.replace): crash giữa lúc serialize không xoá mất lịch sử
    — cùng idiom scheduler/alerts/backlinks/keywords đã dùng."""
    path = _history_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


# ─── DOMAIN HELPERS ──────────────────────────────────────────────────────────

def _norm_domain(netloc: str) -> str:
    """'WWW.Example.com:8080' → 'example.com'"""
    n = (netloc or "").lower().split(":")[0].strip()
    if n.startswith("www."):
        n = n[4:]
    return n


def _domain_of(url: str) -> str:
    netloc = urlparse(url).netloc or (url or "").split("/")[0]
    return _norm_domain(netloc)


# Số URL SERP đầu mỗi từ khóa giữ lại trong rank history (phân tích competitor P2).
# Cắt ở token này khi lưu — check_keyword_rank trả nguyên danh sách, lưu ít đi để
# file history không phình vô hạn.
_TOP_URLS_KEPT = 10


# ─── GIỚI HẠN TẦN SUẤT CHECK (tách riêng khỏi rate_limiter của traffic bot) ──

def can_run_check() -> tuple[bool, str]:
    """Kiểm tra có được chạy lần check xếp hạng mới không."""
    state = _load_history().get("state", {})
    today = date.today().isoformat()
    max_per_day = getattr(cfg, "RANK_CHECK_MAX_PER_DAY", 3)
    min_interval = getattr(cfg, "RANK_CHECK_MIN_INTERVAL", 3600)

    if state.get("date") != today:
        return True, ""
    if state.get("count", 0) >= max_per_day:
        return False, f"Đã đạt giới hạn {max_per_day} lần check xếp hạng/ngày. Chờ ngày mai."
    last = state.get("last_check", 0)
    if last > 0:
        elapsed = time.time() - last
        if elapsed < min_interval:
            return False, f"Cooldown: chờ {int(min_interval - elapsed)}s nữa giữa các lần check."
    return True, ""


def mark_check_run():
    """Ghi nhận đã chạy 1 lần check (reset theo ngày)."""
    h = _load_history()
    today = date.today().isoformat()
    state = h.get("state", {})
    if state.get("date") != today:
        state = {"date": today, "count": 0, "last_check": 0}
    state["count"] = state.get("count", 0) + 1
    state["last_check"] = time.time()
    h["state"] = state
    _save_history(h)


# ─── LẤY KẾT QUẢ ORGANIC TỪ SERP ────────────────────────────────────────────

def _is_skipped_netloc(netloc: str) -> bool:
    return any(s in netloc for s in _SKIP_NETLOC)


async def _extract_organic_hrefs(page: Page) -> list[str]:
    """Trả về danh sách href organic theo đúng thứ tự hiển thị trên SERP."""
    raw: list[str] = []
    for sel in _SERP_SELECTORS:
        try:
            raw = await page.eval_on_selector_all(sel, "els => els.map(e => e.href)")
        except Exception:
            raw = []
        if raw:
            break

    hrefs, seen = [], set()
    for href in raw or []:
        if not href or not href.startswith("http"):
            continue
        # Bóc redirect Google trước khi xét domain (/url?q=https://target...)
        if "/url?q=" in href:
            href = _unwrap_google_redirect(href)
            if not href.startswith("http"):
                continue
        p = urlparse(href)
        netloc = _norm_domain(p.netloc)
        if not netloc or _is_skipped_netloc(netloc):
            continue
        if "webcache" in p.path:
            continue
        key = netloc + p.path
        if key in seen:
            continue
        seen.add(key)
        hrefs.append(href)
    return hrefs


async def check_keyword_rank(page: Page, keyword: str, domain: str, depth: int = 100) -> dict:
    """
    Search 1 từ khóa và tìm vị trí domain trong kết quả organic.
    Returns: {"captcha": bool, "position": int|None, "url": str|None, "scanned": int}
    """
    q = quote(keyword)
    search_url = f"https://www.google.com/search?q={q}&num={depth}&hl=vi&gl=vn&pws=0"

    await page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
    await random_sleep(2.0, 4.0)
    await _accept_google_consent(page)

    if _is_captcha(page):
        return {"captcha": True, "position": None, "url": None, "scanned": 0}

    # Cuộn qua trang để Google render đủ kết quả (và nhìn tự nhiên hơn)
    await human_scroll(page, duration=random.randint(6, 12))

    hrefs = await _extract_organic_hrefs(page)
    position, matched = None, None
    for idx, href in enumerate(hrefs, 1):
        if _norm_domain(urlparse(href).netloc) == domain:
            position, matched = idx, href
            break

    # Top đầu SERP giữ lại cho phân tích competitor (P2): hrefs đã scan sẵn
    # nên việc lưu thêm là 0 request — bỏ đi mới là phí. Giới hạn token để
    # file lịch sử không phình (10 URL / từ khóa là đủ đếm domain nào giành top).
    top_urls = hrefs[:_TOP_URLS_KEPT]

    return {"captcha": False, "position": position, "url": matched, "scanned": len(hrefs),
            "top_urls": top_urls}


# ─── LƯU KẾT QUẢ ─────────────────────────────────────────────────────────────

def save_check_result(results: dict, domain: str):
    """results: {keyword: {"pos": int|None, "url": str|None}}"""
    h = _load_history()
    h["domain"] = domain
    h.setdefault("checks", {})
    # Key đủ độ chính xác microsecond: hai lần check cùng NHỊP GIÂY không ghi đè nhau
    # (mất mốc so sánh của F3). Display chỉ hiện tới giây qua _fmt_stamp ở các consumer.
    h["checks"][datetime.now().isoformat()] = results

    keys = sorted(h["checks"].keys())
    for k in keys[:-MAX_CHECKS_KEPT]:
        del h["checks"][k]
    _save_history(h)


# ─── CHẠY MỘT LẦN CHECK ĐẦY ĐỦ ───────────────────────────────────────────────

async def run_rank_check(page: Page, keywords: list = None, domain: str = None,
                         on_captcha=None) -> tuple[dict, bool]:
    """
    Check toàn bộ từ khóa. Trả về (results, captcha_hit).
    results: {keyword: {"pos": int|None, "url": str|None}}
    on_captcha: async callback(page) -> bool. Trả True nếu đã giải CAPTCHA
                (thử lại từ khóa), False/None để dừng toàn bộ check.
    """
    keywords = keywords or load_keywords()
    domain = domain or _domain_of(getattr(cfg, "TARGET_URL", ""))
    depth = getattr(cfg, "RANK_CHECK_DEPTH", 100)
    delay_min = getattr(cfg, "RANK_KEYWORD_DELAY_MIN", 8)
    delay_max = getattr(cfg, "RANK_KEYWORD_DELAY_MAX", 20)

    if not keywords:
        print("[Rank] ⚠️ Chưa có từ khóa nào (config/keywords.json rỗng).")
        return {}, False
    if not domain:
        print("[Rank] ⚠️ Chưa cấu hình TARGET_URL.")
        return {}, False

    # Xáo trộn thứ tự để tránh pattern lặp giữa các lần check
    order = random.sample(list(keywords), len(keywords))
    print(f"[Rank] === BẮT ĐẦU CHECK: {len(order)} từ khóa | domain {domain} | top {depth} ===")

    results: dict = {}
    captcha_hit = False

    for i, kw in enumerate(order, 1):
        print(f"[Rank] ({i}/{len(order)}) '{kw}' ...")

        r = None
        for attempt in (1, 2):  # tối đa 1 lần retry sau khi giải CAPTCHA
            try:
                r = await check_keyword_rank(page, kw, domain, depth)
            except Exception as e:
                print(f"[Rank]    ⚠️ Lỗi: {str(e)[:80]} — ghi nhận không xếp hạng.")
                break
            if r["captcha"] and on_captcha and attempt == 1:
                try:
                    solved = await on_captcha(page)
                except Exception:
                    solved = False
                if solved:
                    print("[Rank]    ↻ Giải CAPTCHA xong — thử lại từ khóa này...")
                    continue
            break

        if r is None:
            results[kw] = {"pos": None, "url": None}
            continue

        if r["captcha"]:
            print("[Rank] 🚫 Vẫn CAPTCHA — DỪNG check. Kết quả một phần sẽ được lưu.")
            captcha_hit = True
            break

        results[kw] = {"pos": r["position"], "url": r["url"],
                       "top_urls": r.get("top_urls") or []}
        if r["position"]:
            print(f"[Rank]    → Hạng {r['position']}: {r['url'][:70]}")
        elif r["scanned"] == 0:
            print("[Rank]    ⚠️ Google trả về 0 kết quả (consent/CAPTCHA/layout đổi?)")
        else:
            print(f"[Rank]    → Không thấy trong top {r['scanned']} kết quả")

        if i < len(order):
            await random_sleep(delay_min, delay_max)

    if results:
        save_check_result(results, domain)
        print(f"[Rank] Đã lưu kết quả {len(results)}/{len(order)} từ khóa vào rank_history.json.")
        alerts.check_and_notify()   # phải chạy SAU khi lịch sử đã ghi mốc mới

    return results, captcha_hit


# ─── BÁO CÁO ─────────────────────────────────────────────────────────────────

_SPARK_CHARS = "▁▂▃▄▅▆▇█"


def fmt_stamp(key: str) -> str:
    """Key ISO (có/không microsecond) → 'YYYY-MM-DD HH:MM:SS' để hiển thị/CSV."""
    return str(key)[:19].replace("T", " ")


def sparkline(positions: list, width: int = 8) -> str:
    """Vẽ xu hướng: hạng càng tốt (số nhỏ) → cột càng cao. None → '·'"""
    vals = positions[-width:]
    if not vals:
        return ""
    known = [v for v in vals if v is not None]
    if not known:
        return "·" * len(vals)
    hi = max(max(known), 2)
    out = []
    for v in vals:
        if v is None:
            out.append("·")
            continue
        frac = 1.0 - (v - 1) / (hi - 1)
        frac = max(0.0, min(1.0, frac))
        idx = int(frac * (len(_SPARK_CHARS) - 1) + 0.5)
        out.append(_SPARK_CHARS[idx])
    return "".join(out)


def delta_str(cur, prv) -> str:
    """So sánh hạng hiện tại với lần check trước."""
    if cur is None and prv is None:
        return "—"
    if prv is None:
        return "NEW"
    if cur is None:
        return "RỚT"
    d = prv - cur  # dương = hạng tăng (lên)
    if d > 0:
        return f"↑{d}"
    if d < 0:
        return f"↓{-d}"
    return "="


def build_report(tail_spark: int = 8) -> str:
    """Bảng báo cáo xếp hạng: từ khóa | hạng hiện tại | Δ | xu hướng."""
    h = _load_history()
    checks = h.get("checks", {})
    if not checks:
        return "Chưa có dữ liệu xếp hạng. Chạy lần đầu: python main.py --rank"

    keys = sorted(checks.keys())
    latest = keys[-1]
    prev = keys[-2] if len(keys) >= 2 else None
    latest_data = checks[latest]
    prev_data = checks[prev] if prev else {}
    domain = h.get("domain", "?")
    depth = getattr(cfg, "RANK_CHECK_DEPTH", 100)

    lines = []
    lines.append("=" * 76)
    lines.append(f"  BÁO CÁO XẾP HẠNG GOOGLE — {domain}")
    lines.append(f"  Lần check gần nhất: {fmt_stamp(latest)}  "
                 f"({len(keys)} lần lưu | {len(latest_data)} từ khóa)")
    lines.append("=" * 76)
    lines.append(f"  {'Từ khóa':<40}{'Hạng':>7}  {'Δ':>5}  Xu hướng")
    lines.append("-" * 76)

    found_positions = []
    for kw in sorted(latest_data.keys()):
        cur = (latest_data.get(kw) or {}).get("pos")
        prv = (prev_data.get(kw) or {}).get("pos")
        trend = [(checks[k].get(kw) or {}).get("pos") for k in keys[-tail_spark:]]
        pos_str = str(cur) if cur is not None else f">{depth}"
        lines.append(f"  {kw[:40]:<40}{pos_str:>7}  {delta_str(cur, prv):>5}  {sparkline(trend)}")
        if cur is not None:
            found_positions.append(cur)

    lines.append("-" * 76)
    total = len(latest_data)
    if found_positions:
        top3 = sum(1 for p in found_positions if p <= 3)
        top10 = sum(1 for p in found_positions if p <= 10)
        avg = sum(found_positions) / len(found_positions)
        lines.append(f"  Vào top: {len(found_positions)}/{total} từ khóa | "
                     f"Top 3: {top3} | Top 10: {top10} | Hạng TB: {avg:.1f}")
    else:
        lines.append(f"  Chưa từ khóa nào vào top {depth}.")
    return "\n".join(lines)


def print_report():
    print(build_report())


# ─── CLI ENTRY ───────────────────────────────────────────────────────────────

async def _cli_solve_captcha(page: Page) -> bool:
    """Hỏi người dùng giải CAPTCHA trong cửa sổ browser rồi nhấn Enter."""
    print("\n[Rank] 🧩 Google hiện CAPTCHA trong cửa sổ trình duyệt.")
    try:
        ans = await asyncio.to_thread(
            input, "[Rank] Giải xong → nhấn Enter để tiếp tục | g + Enter = bỏ qua: ")
        return ans.strip().lower() != "g"
    except (EOFError, OSError):
        return False


async def run_rank_check_cli(interactive: bool = True):
    """interactive=False cho lịch tự chạy: gặp CAPTCHA thì bỏ qua, không gọi input()."""
    ok, reason = can_run_check()
    if not ok:
        print(f"[Rank] {reason}")
        return

    proxy = None
    if getattr(cfg, "PROXY_LIST", None):
        proxy = cfg.PROXY_LIST[0]
        print(f"[Rank] Dùng proxy: {proxy}")

    from core.browser_manager import BrowserManager

    manager = BrowserManager()
    try:
        browser = await manager.launch_browser()
        page = await manager.create_context(browser, proxy_info=proxy, profile_id="rank_tracker")
        await run_rank_check(page,
                             on_captcha=_cli_solve_captcha if interactive else None)
        mark_check_run()
        print()
        print_report()
    finally:
        await manager.close()
