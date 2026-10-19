"""
utils/pagespeed.py — F6: Core Web Vitals lấy từ PageSpeed Insights API (không key).

PSI nhờ máy chủ Google chạy Lighthouse rồi trả kết quả, nên một lượt mất tới hàng
chục giây: timeout ở đây (PAGESPEED_TIMEOUT) phải lớn hơn timeout crawl
(AUDIT_TIMEOUT) nhiều.

Hai điều phải nhớ khi đọc code này:
- Số liệu là **LAB** (Lighthouse chạy hộ ta), không phải field data CrUX của người
  dùng thật — mọi thông điệp in ra đều ghi rõ chữ "LAB".
- Không key nên quota thấp: 429 là trường hợp bình thường, phải cho ra thông điệp
  tiếng Việt và exit code, không raise, không in response thô (vài MB).

Chạy:
    python main.py --pagespeed [url]      # thiếu url thì lấy TARGET_URL
File: data/pagespeed.json (chỉ số gọn). Cấu hình: config/settings.py PHẦN H.
"""
import json
import os
from datetime import datetime

import requests

import config.settings as cfg
from utils import site_paths

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
CATEGORY = "PERFORMANCE"
STRATEGIES = ("mobile", "desktop")
LAB_NOTE = "số liệu LAB (Lighthouse do Google chạy hộ), không phải field data CrUX"
MESSAGE_MAX = 200              # độ dài tối đa một dòng lỗi — không kéo response vào log
_AUDIT_IDS = {"lcp": "largest-contentful-paint", "cls": "cumulative-layout-shift",
              "inp": "interaction-to-next-paint", "fcp": "first-contentful-paint",
              "tbt": "total-blocking-time"}


def _timeout() -> int:
    try:
        return max(30, int(getattr(cfg, "PAGESPEED_TIMEOUT", 90)))
    except (TypeError, ValueError):
        return 90


def _api_key() -> str:
    """Key PSI (tùy chọn). Rỗng = gọi ẩn danh, dính quota 'Queries per day' dùng chung."""
    return str(getattr(cfg, "PAGESPEED_API_KEY", "") or "").strip()


def _state_path() -> str:
    """Điểm duy nhất sinh path; F10 rẽ sang data/<site>/ khi đã migrate."""
    folder = getattr(cfg, "PAGESPEED_STATE_DIR", "data") or "data"
    if not os.path.isabs(folder):
        folder = os.path.join(ROOT, folder)
    return site_paths.per_site("pagespeed.json", folder)


def _short(value) -> str:
    """Một dòng sạch, ngắn — đủ để chứa message lỗi mà không chứa cả payload."""
    return " ".join(str(value if value is not None else "").split())[:MESSAGE_MAX]


# ─── network (seam duy nhất, test thay thế được) ─────────────────────────────

def _api_get(url: str, params: dict, timeout: int):
    """(status, payload, label) — status 0 = không kết nối được. Không raise."""
    try:
        resp = requests.get(url, params=params, timeout=timeout)
    except Exception as exc:
        return (0, None, type(exc).__name__)
    try:
        payload = resp.json()
    except ValueError:
        payload = None
    return (int(resp.status_code or 0), payload, "")


def build_params(url: str, strategy: str) -> dict:
    """Tham số gọi PSI — 'key' chỉ xuất hiện khi owner tự điền, không có secret nào mặc định."""
    params = {"url": url, "strategy": strategy.upper(), "category": CATEGORY}
    key = _api_key()
    if key:
        params["key"] = key
    return params


def fetch(url: str, strategy: str = "mobile") -> dict:
    """Một lượt đo PSI -> dict gọn. Thất bại cũng ra dict (có 'error'), không None."""
    status, payload, _label = _api_get(API, build_params(url, strategy), _timeout())
    return parse(strategy, url, status, payload)


def _server_message(payload) -> str:
    """Câu Google gửi trong error.message (đã cắt ngắn) — '' khi không có."""
    if not isinstance(payload, dict):
        return ""
    return _short((payload.get("error") or {}).get("message"))


def parse(strategy: str, url: str, status: int, payload) -> dict:
    """(status, payload) thô -> {url, strategy, score, lcp, cls, inp, fcp, tbt, error}."""
    data = {"url": url, "strategy": strategy, "score": None,
            "lcp": "", "cls": "", "inp": "", "fcp": "", "tbt": "", "error": ""}
    if status == 0:
        data["error"] = "Không kết nối được tới PageSpeed Insights (mạng hoặc proxy)"
        return data
    if status == 429:
        message = _server_message(payload)
        hint = "" if _api_key() else " — đặt PAGESPEED_API_KEY (miễn phí) để thoát quota dùng chung"
        data["error"] = ("PSI trả 429 — hết quota (gọi không key nên giới hạn rất thấp),"
                         " thử lại sau ít phút" + hint + (f" — Google: {message}" if message else ""))
        return data
    if not isinstance(payload, dict):
        data["error"] = f"PSI trả HTTP {status} mà không có JSON hợp lệ — thử lại sau"
        return data
    result = payload.get("lighthouseResult")
    if not isinstance(result, dict):
        message = _server_message(payload)
        tail = f": {message}" if message else " — thử lại, URL có thể không tải được"
        data["error"] = f"PSI không trả kết quả Lighthouse (HTTP {status}){tail}"
        return data
    audits = result.get("audits") or {}
    for key, audit_id in _AUDIT_IDS.items():
        data[key] = _short((audits.get(audit_id) or {}).get("displayValue"))
    data["score"] = _score(result, audits)
    return data


def _score(result: dict, audits: dict):
    """Điểm performance 0-100: ưu tiên categories.performance, fallback audit đồng tên."""
    value = ((result.get("categories") or {}).get("performance") or {}).get("score")
    if value is None:
        value = (audits.get("performance-score") or {}).get("score")
    try:
        return int(round(float(value) * 100))
    except (TypeError, ValueError):
        return None


# ─── file (chỉ số gọn, không bao giờ là response thô) ────────────────────────

def save(report: dict) -> str:
    path = _state_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    # Ghi qua .tmp rồi os.replace: chết giữa chừng (Ctrl-C, scheduler kill) không để lại
    # JSON cụt — load_saved() gặp file hỏng là trả None im lặng nên báo cáo cũ sẽ mất sạch.
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
    return path


def load_saved():
    """Báo cáo gần nhất hoặc None — file thiếu/hỏng đều im lặng trả None."""
    path = _state_path()
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("url") else None


# ─── CLI ─────────────────────────────────────────────────────────────────────

def _line(result: dict) -> str:
    name = result["strategy"]
    if result["error"]:
        return f"[PageSpeed] {name:<8}: {result['error']}"
    score = "—" if result["score"] is None else str(result["score"])
    return (f"[PageSpeed] {name:<8}: điểm {score}/100 | LCP {result['lcp'] or '—'}"
            f" | CLS {result['cls'] or '—'} | INP {result['inp'] or '—'}"
            f" | FCP {result['fcp'] or '—'} | TBT {result['tbt'] or '—'}")


def run_pagespeed_cli(url: str = "") -> int:
    """Entry `--pagespeed`: đo mobile + desktop, in số gọn, lưu data/pagespeed.json."""
    target = (url or getattr(cfg, "TARGET_URL", "") or "").strip()
    if not target:
        print("[PageSpeed] ⚠️ Chưa đặt TARGET_URL trong config/settings.py — không biết đo site nào.")
        return 2

    print(f"[PageSpeed] Đo {target} qua PSI v5 (không key, mobile + desktop,"
          f" timeout {_timeout()}s/lượt) — có thể mất tới hơn một phút")
    results = {strategy: fetch(target, strategy) for strategy in STRATEGIES}
    for strategy in STRATEGIES:
        print(_line(results[strategy]))

    ok = [name for name, result in results.items() if not result["error"]]
    if not ok:
        print("[PageSpeed] ❌ Không lấy được số liệu nào — báo cáo --audit vẫn chạy độc lập.")
        return 1

    report = {"url": target, "fetched_at": datetime.now().isoformat(timespec="seconds"),
              "lab": True}
    report.update(results)
    path = save(report)
    shown = os.path.relpath(path, ROOT)
    print(f"[PageSpeed] ✅ Đã lưu {shown} — {'/'.join(ok)} thành công.")
    for strategy in STRATEGIES:
        if results[strategy]["error"]:
            print(f"[PageSpeed] ⚠️ {strategy} thiếu: {results[strategy]['error']}")
    print(f"[PageSpeed] Ghi chú: {LAB_NOTE}.")
    return 0


# ─── T33: PageSpeed cho bài vừa push — 1 request/URL TRỌN ĐỜI, nhắc khi yếu ──
# Lớp trên F6: cùng seam fetch()/parse(), state riêng pagespeed_posts.json
# (không đụng data/pagespeed.json của F6 — nơi lưu --pagespeed 1 URL).
# Đo MOBILE (Google index mobile-first); desktop đo tay bằng --pagespeed URL.
# Mỗi bài trong wp_pushed.json đo đúng MỘT LẦN thành công rồi ghi key — job
# sau đó bỏ qua (0 request); lỗi không ghi state nên lần chạy kế thử lại.
# Điểm yếu (< PAGESPEED_WARN_SCORE) → 1 dòng nhắc trong báo cáo ngày.


def _default_posts_path() -> str:
    folder = getattr(cfg, "PAGESPEED_STATE_DIR", "data") or "data"
    if not os.path.isabs(folder):
        folder = os.path.join(ROOT, folder)
    return site_paths.per_site("pagespeed_posts.json", folder)


POSTS_FILE = _default_posts_path()      # test gán POSTS_FILE → _posts_path() tôn trọng


def _posts_path() -> str:
    if POSTS_FILE != _default_posts_path():
        return POSTS_FILE
    return _default_posts_path()


def _norm_post_key(url: str) -> str:
    """Key bài đo = host + path bỏ query + '/' cuối — wp_pushed ↔ state khớp nhau."""
    try:
        from urllib.parse import urlsplit
        p = urlsplit(str(url or ""))
        return f"{p.netloc}{p.path}".rstrip("/").lower()
    except Exception:
        return str(url or "").lower().rstrip("/")


def posts_load() -> dict:
    """{"urls": {key: {url, kw, at, score, lcp, cls, tbt, fcp}}} — hỏng → rỗng."""
    try:
        with open(_posts_path(), encoding="utf-8") as handle:
            data = json.load(handle)
        urls = data.get("urls") if isinstance(data, dict) else None
        return {"urls": urls if isinstance(urls, dict) else {}}
    except Exception:
        return {"urls": {}}


def posts_save(data: dict) -> None:
    """Atomic (tmp + os.replace) — crash giữa chừng không cụt file."""
    path = _posts_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def posts_to_measure(limit: int = None, pushed: dict = None) -> list:
    """Bài đã push CHƯA có điểm → [{url, kw, key}]; chặn limit mỗi lần chạy."""
    if limit is None:
        try:
            limit = int(getattr(cfg, "PAGESPEED_MAX_PER_RUN", 5) or 5)
        except (TypeError, ValueError):
            limit = 5
    if pushed is None:
        try:
            from utils.plan_progress import load_pushed as _load_pushed
            pushed = _load_pushed()
        except Exception:
            pushed = {}
    known = set(posts_load()["urls"])
    out = []
    for fk, entry in (pushed or {}).items():
        entry = entry if isinstance(entry, dict) else {}
        link = str(entry.get("link") or "").strip()
        if not link.startswith(("http://", "https://")):
            continue
        key = _norm_post_key(link)
        if not key or key in known:
            continue
        out.append({"url": link, "kw": str(entry.get("keyword") or fk), "key": key})
        if limit and len(out) >= limit:
            break
    return out


def _record_from(result: dict, it: dict) -> dict:
    return {"url": it["url"], "kw": it["kw"], "key": it["key"],
            "at": datetime.now().isoformat(timespec="seconds"),
            "score": result.get("score"),
            "lcp": str(result.get("lcp") or ""), "cls": str(result.get("cls") or ""),
            "tbt": str(result.get("tbt") or ""), "fcp": str(result.get("fcp") or "")}


def measure_new_posts(fetcher=None, limit: int = None, pushed: dict = None) -> tuple:
    """(results, stop_note) — đo đợt bài chưa có điểm; thành công mới GHI state
    (1 lần/URL). Lỗi từng bài không chặn, PSI 429 → dừng cả đợt (quota cạn,
    chạy tiếp vô nghĩa — URL chưa ghi, lần kế thử lại). fetcher=None → fetch thật."""
    runner = fetcher or fetch
    todo = posts_to_measure(limit, pushed=pushed)
    recorder = posts_load()
    results = []
    stop_note = ""
    for it in todo:
        try:
            result = runner(it["url"], "mobile")
        except Exception as exc:      # fetcher ném exception — coi như lỗi lượt này
            result = {"error": f"{type(exc).__name__}: {exc}"}
        result = result if isinstance(result, dict) else {}
        rec = _record_from(result, it)
        error = str(result.get("error") or "")
        if error:
            results.append({**rec, "error": error})
            if error.startswith("PSI trả 429"):
                stop_note = ("PSI 429 — dừng đợt này (quota); URL chưa ghi, lần "
                             "--run-job pagespeed kế tiếp tự thử lại.")
                break
            continue                  # lỗi khác — không ghi state, bỏ qua bài này
        recorder["urls"][it["key"]] = rec
        posts_save(recorder)
        results.append(rec)
    return results, stop_note


def weak_posts() -> list:
    """Nhắc cho báo cáo ngày: bài điểm LAB < PAGESPEED_WARN_SCORE — tối đa 2 dòng,
    kém nhất lên trước. Không nhắc bài chưa đo (job tự đo) hay đã đạt."""
    warn = int(getattr(cfg, "PAGESPEED_WARN_SCORE", 60) or 60)
    rows = sorted(posts_load()["urls"].values(),
                  key=lambda r: (r.get("score") if isinstance(r.get("score"), int) else 999,
                                 str(r.get("at") or "")))
    lines = []
    for r in rows:
        score = r.get("score")
        if not isinstance(score, int) or score >= warn:
            continue
        lcp = f", LCP {r['lcp']}" if r.get("lcp") else ""
        kw = str(r.get("kw") or r.get("url") or "")[:50]
        lines.append(f"- Bài '{kw}' PageSpeed LAB {score}/100{lcp} — "
                     "cải thiện rồi đo lại: python main.py --pagespeed-posts \""
                     + str(r.get("url") or "") + "\"")
        if len(lines) >= 2:
            break
    return lines


def reminder_lines() -> list:
    """Tên đẹp cho daily_report — cùng ý weak_posts() (không đo lại là không nhắc thêm)."""
    return weak_posts()


def posts_report_text() -> str:
    """Bảng điểm bài đã đo — kém nhất lên trước, đủ sạch để paste Telegram."""
    rows = sorted(posts_load()["urls"].values(),
                  key=lambda r: (r.get("score") if isinstance(r.get("score"), int) else 999,
                                 str(r.get("at") or "")))
    if not rows:
        return ("Chưa đo bài nào — job scheduler 'pagespeed' tự đo bài mới sau "
                "--wp-push; chạy đợt ngay: python main.py --run-job pagespeed")
    lines = [f"== PAGESPEED BÀI VIẾT ({len(rows)} bài đã đo, LAB mobile — {LAB_NOTE}) ==",
             f'{"Bài":<34}{"Điểm":>6}{"LCP":>8}{"CLS":>7}  URL', "-" * 104]
    for r in rows:
        score = "—" if not isinstance(r.get("score"), int) else str(r["score"])
        kw = str(r.get("kw") or "")[:32]
        lines.append(f'{kw:<34}{score:>6}{r["lcp"][:6]:>8}{r["cls"][:5]:>7}  {r["url"]}')
    weak = weak_posts()
    if weak:
        lines.append("")
        lines.append("Điểm yếu (nhắc trong báo cáo ngày):")
        lines.extend(weak)
    return "\n".join(lines)


def run_pagespeed_posts_cli(url: str = "") -> int:
    """Entry `--pagespeed-posts`: không URL = đo đợt bài mới (đúng job scheduler);
    có URL = ĐO LẠI bài đó (xóa điểm cũ, 1 request mới) rồi in điểm."""
    target = str(url or "").strip()
    if target:
        key = _norm_post_key(target)
        data = posts_load()
        if data["urls"].pop(key, None):
            posts_save(data)
            print(f"[PageSpeed] Đã xóa điểm cũ {key} — đo lại...")
        else:
            print(f"[PageSpeed] Đo tay thêm: {key}")
        try:
            result = fetch(target, "mobile")
        except Exception as exc:
            print(f"[PageSpeed] ❌ {type(exc).__name__}: {exc}")
            return 1
        if result.get("error"):
            print(f"[PageSpeed] ❌ {result['error']}")
            return 1
        data = posts_load()
        data["urls"][key] = _record_from(result, {"url": target, "kw": "", "key": key})
        posts_save(data)
        print(f"[PageSpeed] Điểm {result.get('score')}/100 | LCP {result['lcp']} | "
              f"CLS {result['cls']} (LAB mobile)")
        print("[PageSpeed] Đã ghi — xem hết: python main.py --pagespeed-posts")
        return 0

    results, stop_note = measure_new_posts()
    if not results and not stop_note:
        print("[PageSpeed] Bài nào push WP cũng đã có điểm — 1 request/URL trọn đời, 0 request lần này.")
        return 0
    for r in results:
        if r.get("error"):
            print(f"[PageSpeed] ⚠️ {str(r['kw'])[:40]}: {r['error']}")
        else:
            print(f"[PageSpeed] {str(r['kw'])[:40]}: điểm {r['score']}/100 | "
                  f"LCP {r['lcp']} | CLS {r['cls']}")
    if stop_note:
        print(f"[PageSpeed] {stop_note}")
    try:
        from utils.plan_progress import load_pushed as _load_pushed
        pushed = _load_pushed() or {}
        total = sum(1 for p in pushed.values() if isinstance(p, dict)
                    and str(p.get("link") or "").startswith(("http://", "https://")))
        print(f"[PageSpeed] Đã đo {len(posts_load()['urls'])}/{total} bài push WP (1 lần/URL).")
    except Exception:
        pass
    print("[PageSpeed] Ghi chú: " + LAB_NOTE + ". Điểm yếu sẽ nhắc trong báo cáo ngày.")
    return 0
