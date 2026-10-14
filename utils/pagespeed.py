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
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
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
