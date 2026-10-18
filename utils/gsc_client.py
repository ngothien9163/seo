"""
utils/gsc_client.py — Google Search Console API client (dữ liệu SEO thật, không scrape).

Luồng:
1. Đọc service account JSON key từ config/gsc_service_account.json (xem docs/SETUP_GSC.md)
2. Lấy access token bằng google-auth (scope webmasters.readonly, tự refresh)
3. POST searchAnalytics/query: clicks/impressions/position/CTR theo query
4. Lưu snapshot/ngày vào gsc_history.json (giữ 90 ngày) + rate limit riêng

Chạy:
    python main.py --gsc          # Fetch + in báo cáo gộp
    python main.py --gsc-report   # Chỉ xem báo cáo đã lưu
    GUI: tab "📈 Xếp Hạng" → nút "📊 Lấy Dữ Liệu Search Console"

Ghi chú:
- Đồng bộ thuần HTTP (requests) — KHÔNG dùng Playwright/browser, không CAPTCHA.
- google-auth import lười (trong hàm) — module vẫn load được khi chưa cài thư viện.
- Token chỉ nằm trong bộ nhớ, không in ra console.
"""
import json
import os
import sys
import time
from datetime import date, datetime, timedelta
from urllib.parse import quote

import requests

import config.settings as cfg
import utils.site_paths as _site_paths

_GSC_NAME = "gsc_history.json"
_DEFAULT_GSC_PATH = _site_paths.site_file(_GSC_NAME)
# Slot override cho test/CLI (test gán DATA_FILE); code đọc qua _data_path().
HISTORY_FILE = DATA_FILE = _DEFAULT_GSC_PATH


def _data_path() -> str:
    """Đường dẫn gsc history lúc gọi. Test gán DATA_FILE → tôn trọng; không → resolve per-site."""
    if DATA_FILE != _DEFAULT_GSC_PATH:
        return DATA_FILE
    return _site_paths.site_file(_GSC_NAME)

GSC_API_BASE = "https://searchconsole.googleapis.com/webmasters/v3/sites"
SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
MAX_SNAPSHOTS_KEPT = 90  # Số ngày snapshot lưu lại tối đa

_CREDENTIALS = None  # cache credentials trong suốt phiên (token tự quản refresh)


class GSCSetupError(Exception):
    """Thiếu/sai credentials — cần làm docs/SETUP_GSC.md."""


# ─── LỊCH SỬ: đọc / ghi ──────────────────────────────────────────────────────

def _load_history() -> dict:
    path = _data_path()
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"site": "", "snapshots": {}, "state": {"date": "", "count": 0, "last_fetch": 0}}


def _save_history(data: dict):
    """Ghi nguyên tử (tmp + os.replace): crash giữa lúc serialize không xoá mất snapshot
    GSC đã tích luỹ — cùng idiom scheduler/alerts/backlinks/keywords."""
    path = _data_path()
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


# ─── CREDENTIALS ─────────────────────────────────────────────────────────────

def _resolve_path(p: str) -> str:
    """Path tương đối trong config → resolve theo thư mục gốc project."""
    if os.path.isabs(p):
        return p
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", p))


def _setup_guide_msg() -> str:
    return (
        "Chưa có credentials Google Search Console.\n"
        "Hướng dẫn setup từng bước: docs/SETUP_GSC.md\n"
        f"Tóm tắt: đặt service account JSON key vào '{_resolve_path(getattr(cfg, 'GSC_CREDENTIALS_FILE', ''))}' "
        "rồi thêm email service account vào Search Console property (quyền Restricted là đủ)."
    )


def load_credentials():
    """Đọc service account JSON key → credentials object (scope readonly)."""
    global _CREDENTIALS
    if _CREDENTIALS is not None:
        return _CREDENTIALS

    path = _resolve_path(getattr(cfg, "GSC_CREDENTIALS_FILE", ""))
    if not path or not os.path.exists(path):
        raise GSCSetupError(_setup_guide_msg())

    from google.oauth2 import service_account  # import lười — không chặn module
    try:
        _CREDENTIALS = service_account.Credentials.from_service_account_file(path, scopes=[SCOPE])
    except Exception as e:
        raise GSCSetupError(f"File credentials '{path}' lỗi: {e}\n{_setup_guide_msg()}")
    return _CREDENTIALS


def _get_token(creds, force_refresh: bool = False) -> str:
    """Access token Bearer từ credentials (refresh nếu chưa có / hết hạn / ép)."""
    if force_refresh or not creds.token:
        from google.auth.transport.requests import Request  # import lười
        creds.refresh(Request())
    return creds.token


# ─── RATE LIMIT (tách riêng khỏi rate_limiter traffic bot) ──────────────────

def can_run_fetch() -> tuple[bool, str]:
    state = _load_history().get("state", {})
    today = date.today().isoformat()
    max_per_day = getattr(cfg, "GSC_MAX_FETCH_PER_DAY", 4)

    if state.get("date") != today:
        return True, ""
    if state.get("count", 0) >= max_per_day:
        return False, f"Đã đạt giới hạn {max_per_day} lần fetch Search Console/ngày. Dữ liệu hôm nay đã được lưu — dùng --gsc-report."
    return True, ""


def mark_fetch_run():
    h = _load_history()
    today = date.today().isoformat()
    state = h.get("state", {})
    if state.get("date") != today:
        state = {"date": today, "count": 0, "last_fetch": 0}
    state["count"] = state.get("count", 0) + 1
    state["last_fetch"] = time.time()
    h["state"] = state
    _save_history(h)


# ─── GỌI API ─────────────────────────────────────────────────────────────────

def parse_api_response(payload: dict) -> dict:
    """JSON response của searchAnalytics/query → {query: {clicks, impressions, position, ctr}}."""
    out: dict = {}
    for row in (payload or {}).get("rows") or []:
        keys = row.get("keys") or []
        if not keys:
            continue
        q = str(keys[0])
        out[q] = {
            "clicks": int(row.get("clicks") or 0),
            "impressions": int(row.get("impressions") or 0),
            "position": float(row.get("position") or 0.0),
            "ctr": float(row.get("ctr") or 0.0),
        }
    return out


def parse_qp_response(payload: dict) -> dict:
    """Response dimensions=["query","page"] → {query: [{page, clicks, imps}]}.
    Mỗi hàng là một cặp (query, page) — gom theo query; hàng thiếu page bị bỏ
    (GSC trả page rỗng cho dòng tổng, không phải trang thật)."""
    out: dict = {}
    for row in (payload or {}).get("rows") or []:
        keys = row.get("keys") or []
        if len(keys) < 2:
            continue
        q, page = str(keys[0]), str(keys[1])
        if not q or not page:
            continue
        out.setdefault(q, []).append({
            "page": page,
            "clicks": int(row.get("clicks") or 0),
            "imps": int(row.get("impressions") or 0),
        })
    return out


def _query_url() -> str:
    site = quote(getattr(cfg, "GSC_SITE_URL", ""), safe="")
    return f"{GSC_API_BASE}/{site}/searchAnalytics/query"


def _search_body(days: int, dimensions: list) -> dict:
    return {
        "startDate": (date.today() - timedelta(days=days - 1)).isoformat(),
        "endDate": date.today().isoformat(),
        "dimensions": dimensions,
        "rowLimit": 250,
        "dataState": "all",
    }


def _post_search(body: dict) -> dict:
    """POST searchAnalytics/query — 401 → refresh token 1 lần rồi thử lại.
    Đồng bộ, raise GSCSetupError / requests.HTTPError / RequestException."""
    creds = load_credentials()
    headers = {"Authorization": f"Bearer {_get_token(creds)}"}
    resp = requests.post(_query_url(), json=body, headers=headers, timeout=30)
    if resp.status_code == 401:  # token hết hạn — refresh 1 lần rồi thử lại
        headers = {"Authorization": f"Bearer {_get_token(creds, force_refresh=True)}"}
        resp = requests.post(_query_url(), json=body, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_search_analytics(days: int = None) -> dict:
    """
    Gọi Search Analytics API lấy dữ liệu `days` ngày gần nhất theo query.
    Đồng bộ. Raise GSCSetupError (thiếu credentials) / requests.HTTPError (lỗi API).
    401 → refresh token 1 lần rồi thử lại.
    """
    if days is None:
        days = getattr(cfg, "GSC_LOOKBACK_DAYS", 28)

    return parse_api_response(_post_search(_search_body(days, ["query"])))


def fetch_query_page(days: int = None) -> dict:
    """Fetch thứ hai cùng lần chạy (G-1): dimensions=["query","page"] →
    {query: [{page, clicks, imps}]} — dữ liệu cho G-2 cannibalization.
    Lỗi API/mạng raise cho caller quyết (fetch query thành công thì snapshot
    query vẫn được lưu — dữ liệu theo trang chỉ là bù, không chặn)."""
    if days is None:
        days = getattr(cfg, "GSC_LOOKBACK_DAYS", 28)

    return parse_qp_response(_post_search(_search_body(days, ["query", "page"])))


# ─── LƯU SNAPSHOT ────────────────────────────────────────────────────────────

def save_snapshot(rows: dict, start_date: str, end_date: str, pages: dict = None):
    """Lưu 1 snapshot/ngày (key = ngày fetch). Ghi đè snapshot cùng ngày. Prune quá 90 ngày.
    `pages` (G-1) là dữ liệu theo (query, page) — snapshot cũ không có field này."""
    h = _load_history()
    h["site"] = getattr(cfg, "GSC_SITE_URL", "")
    h.setdefault("snapshots", {})
    snap = {
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "start_date": start_date,
        "end_date": end_date,
        "rows": rows,
    }
    if pages:  # rỗng/None → không ghi field (snapshot cũ giữ nguyên hình dáng)
        snap["pages"] = pages
    h["snapshots"][date.today().isoformat()] = snap
    keys = sorted(h["snapshots"].keys())
    for k in keys[:-MAX_SNAPSHOTS_KEPT]:
        del h["snapshots"][k]
    _save_history(h)


# ─── MATCHING: query GSC ↔ từ khóa cấu hình ─────────────────────────────────

def _fold(s: str) -> str:
    """Fold Unicode: đ/Đ→d/D (không phải combining mark nên NFD không tách được),
    bỏ dấu tiếng Việt (NFD + loại ký tự combining), lowercase, gộp khoảng trắng.
    'Nối Mi Thủ Đức' → 'noi mi thu duc' — khớp cả kiểu gõ không dấu đ→d của người Việt."""
    import unicodedata
    s = (s or "").replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return " ".join(s.lower().split())


def _match_keywords(rows: dict, keywords: list) -> tuple[dict, dict]:
    """
    Gán mỗi query GSC vào đúng MỘT keyword cấu hình.
    Exact (sau khi fold) ưu tiên; sau đó match 'chứa' 2 chiều, chọn keyword ngắn nhất
    (trùng độ dài → theo thứ tự trong list). Keyword khớp nhiều query → giữ query có
    impressions cao nhất làm đại diện.
    Returns: (matched {kw: row}, unmatched {query: row})
    """
    folds = {kw: _fold(kw) for kw in keywords}
    assign: dict = {}  # query -> kw
    for q in rows:
        qf = _fold(q)
        exact = [kw for kw, kf in folds.items() if qf == kf]
        if exact:
            assign[q] = exact[0]
            continue
        cands = [kw for kw, kf in folds.items() if kf and (kf in qf or qf in kf)]
        if cands:
            assign[q] = min(cands, key=lambda k: (len(folds[k]), keywords.index(k)))

    best: dict = {}  # kw -> row (imps cao nhất)
    for q, kw in assign.items():
        row = rows[q]
        if kw not in best or row.get("impressions", 0) > best[kw].get("impressions", 0):
            best[kw] = row

    matched = {kw: best[kw] for kw in best}
    unmatched = {q: rows[q] for q in rows if q not in assign}
    return matched, unmatched


# ─── ĐỀ XUẤT TỪ KHÓA MỚI (F2) ───────────────────────────────────────────────

def latest_gsc_rows() -> dict:
    """rows của snapshot Search Console mới nhất — {} khi chưa từng fetch."""
    snaps = _load_history().get("snapshots", {})
    if not snaps:
        return {}
    return snaps[sorted(snaps.keys())[-1]].get("rows", {}) or {}


def suggest_keywords(rows: dict, tracked: list = None,
                     min_impressions: int = None, limit: int = 20) -> list[dict]:
    """
    Query đang có impressions mà CHƯA theo dõi → ứng viên từ khóa mới.

    rows: {query: {clicks, impressions, position, ctr}} (thường lấy từ latest_gsc_rows())
    tracked: danh sách từ khóa đang theo dõi — None → đọc config/keywords.json
    min_impressions: None → cfg.KEYWORD_SUGGEST_MIN_IMPRESSIONS (ngưỡng inclusive)
    Trả về list [{"query", "impressions", "clicks", "position", "ctr"}] theo impressions giảm dần.
    """
    if tracked is None:
        from utils.keywords import load_keywords
        tracked = load_keywords()
    if min_impressions is None:
        min_impressions = getattr(cfg, "KEYWORD_SUGGEST_MIN_IMPRESSIONS", 30)

    _, unmatched = _match_keywords(rows or {}, list(tracked))
    out = [{"query": q,
            "impressions": r.get("impressions", 0),
            "clicks": r.get("clicks", 0),
            "position": r.get("position", 0.0),
            "ctr": r.get("ctr", 0.0)}
           for q, r in unmatched.items() if r.get("impressions", 0) >= min_impressions]
    out.sort(key=lambda d: (-d["impressions"], d["query"]))
    return out[:limit]


# ─── BÁO CÁO GỘP ─────────────────────────────────────────────────────────────

def build_report(tail_spark: int = 8) -> str:
    """
    Báo cáo gộp: GSC 28 ngày gần nhất (clicks/impressions/vị trí TB/CTR) × lần check
    SERP mới nhất của rank_tracker (hạng + xu hướng).
    """
    from utils.rank_tracker import sparkline, delta_str  # import lười (tránh kéo playwright lúc load module)

    gsc_h = _load_history()
    snaps = gsc_h.get("snapshots", {})
    if not snaps:
        # Chưa có dữ liệu GSC: báo SERP vẫn chạy (ai đó có rank data cũng nên thấy),
        # nhưng phải nói rõ PHẦN GSC đang trống — nguyên verb của rank report
        # ("Chưa có dữ liệu xếp hạng") từng làm tưởng GSC chết vì copy-paste.
        from utils.rank_tracker import build_report as rank_report
        return (rank_report()
                + "\n\n  [Search Console] BÁO CÁO GỘP không có phần GSC — chưa fetch lần nào."
                  "\n  Setup: docs/SETUP_GSC.md | Lấy lần đầu: python main.py --gsc")

    latest_key = sorted(snaps.keys())[-1]
    snap = snaps[latest_key]
    rows = snap.get("rows", {})
    if not rows:
        return (f"Property {gsc_h.get('site') or getattr(cfg, 'GSC_SITE_URL', '?')} chưa có dữ liệu "
                f"(mới verify cần chờ vài ngày để tích lũy). Lần fetch gần nhất: {latest_key}")

    from utils.keywords import load_keywords
    keywords = load_keywords()
    depth = getattr(cfg, "RANK_CHECK_DEPTH", 100)
    matched, unmatched = _match_keywords(rows, keywords)

    # F9 — cột AI (AEO): chưa dán câu trả lời nào → bảng y như trước (không breaking).
    try:
        from utils.aeo import ai_matrix
        ai = ai_matrix()
    except Exception:
        ai = {}
    has_ai = bool(ai)

    # Rank history (có thể không tồn tại — cột SERP sẽ là '—')
    rchecks: dict = {}
    try:
        from utils.rank_tracker import _load_history as _load_rank_history
        rchecks = _load_rank_history().get("checks", {})
    except Exception:
        rchecks = {}
    rkeys = sorted(rchecks.keys())
    rank_latest = rchecks[rkeys[-1]] if rkeys else {}
    rank_prev = rchecks[rkeys[-2]] if len(rkeys) >= 2 else {}

    lines = []
    site = gsc_h.get("site") or getattr(cfg, "GSC_SITE_URL", "?")
    lines.append("=" * 104)
    lines.append(f"  BÁO CÁO SEO GỘP — SERP + SEARCH CONSOLE — {site}")
    lines.append(f"  Dữ liệu GSC: {snap.get('start_date')} → {snap.get('end_date')}"
                 f"  (fetch: {snap.get('fetched_at', '?').replace('T', ' ')})"
                 f"  | Lần check SERP: {rkeys[-1][:19].replace('T', ' ') if rkeys else '—'}")
    lines.append("=" * 104)

    def _serp_cols(kw: str) -> str:
        cur = (rank_latest.get(kw) or {}).get("pos")
        prv = (rank_prev.get(kw) or {}).get("pos")
        trend = [(rchecks[k].get(kw) or {}).get("pos") for k in rkeys[-tail_spark:]]
        pos = str(cur) if cur is not None else "—"
        return f"{pos:>6}  {delta_str(cur, prv):>5}  {sparkline(trend) if trend else '—':<8}"

    def _gsc_cols(row: dict) -> str:
        return (f"{row.get('clicks', 0):>7}"
                f"{row.get('impressions', 0):>7}"
                f"{row.get('position', 0.0):>10.1f}"
                f"{row.get('ctr', 0.0) * 100:>6.1f}%")

    def _ai_cols(kw: str) -> str:
        # n engine đã hỏi: "✓2/3" = 2 nhắc trên 3 engine; chưa có → '—'
        per = ai.get(kw) or {}
        if not per:
            return f"{'—':>6}"
        got = sum(1 for v in per.values() if v.get("mentioned"))
        return f"{f'✓{got}/{len(per)}':>6}"

    if has_ai:
        lines.append(f"  {'Từ khóa':<34}{'SERP':>6}  {'Δ':>5}  {'Xu hướng':<8}"
                     f"{'AI':>6}{'Clicks':>7}{'Hiện':>7}{'Vị trí TB':>10}{'CTR':>7}")
    else:
        lines.append(f"  {'Từ khóa':<34}{'SERP':>6}  {'Δ':>5}  {'Xu hướng':<8}"
                     f"{'Clicks':>7}{'Hiện':>7}{'Vị trí TB':>10}{'CTR':>7}")
    lines.append("-" * (111 if has_ai else 104))

    for kw in sorted(set(keywords) | set(matched.keys())):
        row = matched.get(kw)
        gsc_cols = _gsc_cols(row) if row else f"{'—':>7}{'—':>7}{'—':>10}{'—':>7}"
        ai_cols = _ai_cols(kw) if has_ai else ""
        lines.append(f"  {kw[:34]:<34}{_serp_cols(kw)}{ai_cols}{gsc_cols}")

    if unmatched:
        lines.append("-" * 104)
        lines.append("  Query mới phát hiện (chưa theo dõi) — top theo impressions:")
        top = sorted(unmatched.items(), key=lambda kv: kv[1].get("impressions", 0), reverse=True)[:15]
        for q, r in top:
            lines.append(f"    {q[:50]:<50}{r.get('impressions', 0):>7} hiện{r.get('clicks', 0):>7} clicks"
                         f"  (vị trí TB {r.get('position', 0.0):.1f})")
        lines.append(f"  Biến query thành từ khóa theo dõi (ngưỡng ≥ {getattr(cfg, 'KEYWORD_SUGGEST_MIN_IMPRESSIONS', 30)} "
                     f"impressions): python main.py --gsc-keywords")

    lines.append("-" * 104)
    total_clicks = sum(r.get("clicks", 0) for r in rows.values())
    total_imps = sum(r.get("impressions", 0) for r in rows.values())
    lines.append(f"  Tổng {getattr(cfg, 'GSC_LOOKBACK_DAYS', 28)} ngày (các query trong báo cáo): "
                 f"{total_clicks} clicks | {total_imps} impressions")
    lines.append("  Lưu ý: dữ liệu GSC thường trễ 2–3 ngày so với hiện tại.")
    return "\n".join(lines)


def print_report():
    print(build_report())


# ─── CLI ─────────────────────────────────────────────────────────────────────

def _explain_http_error(status: int) -> str:
    """Thông điệp tiếng Việt cho các lỗi HTTP thường gặp của Search Console API."""
    if status == 403:
        return ("[GSC] Lỗi 403 PERMISSION_DENIED — email service account chưa được thêm vào "
                "Search Console property (quyền 'Restricted' là đủ), hoặc Search Console API "
                "chưa bật trong Google Cloud Console. Xem docs/SETUP_GSC.md bước 3 và 5.")
    if status == 400:
        return ("[GSC] Lỗi 400 BAD_REQUEST — kiểm tra GSC_SITE_URL trong config/settings.py: "
                "phải đúng định dạng 'sc-domain:tenmien.com' hoặc 'https://...' và TRÙNG với "
                "property đã verify trong Search Console.")
    if status == 429:
        return "[GSC] Lỗi 429 — hết quota API. Chờ vài phút rồi thử lại (quota mặc định 1200 req/phút)."
    return f"[GSC] Lỗi HTTP {status} từ Search Console API — chi tiết xem response trong log trên."


def run_gsc_fetch_cli():
    """Entry CLI: rate limit → fetch → lưu snapshot → in báo cáo gộp."""
    ok, reason = can_run_fetch()
    if not ok:
        print(f"[GSC] {reason}")
        return

    site = getattr(cfg, "GSC_SITE_URL", "?")
    days = getattr(cfg, "GSC_LOOKBACK_DAYS", 28)
    print(f"[GSC] Đang lấy dữ liệu Search Console: {site} ({days} ngày gần nhất)...")

    try:
        rows = fetch_search_analytics(days)
    except GSCSetupError as e:
        print(f"[GSC] ❌ {e}")
        sys.exit(1)
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else 0
        print(_explain_http_error(status))
        sys.exit(1)
    except requests.RequestException as e:
        print(f"[GSC] ❌ Lỗi mạng: {str(e)[:120]} — giữ dữ liệu cũ, thử lại sau.")
        sys.exit(1)

    n = len(rows)
    total_clicks = sum(r["clicks"] for r in rows.values())
    total_imps = sum(r["impressions"] for r in rows.values())
    print(f"[GSC] ✅ Nhận {n} query | {total_clicks} clicks | {total_imps} impressions")

    # Dữ liệu theo (query, page) trong CHÙM fetch này (G-1) — lỗi không chặn
    # query snapshot: query là kim chỉ nam chính của tool.
    pages = {}
    try:
        pages = fetch_query_page(days)
        print(f"[GSC] ✅ Dữ liệu theo trang: {sum(len(v) for v in pages.values())} cặp (query, page)")
    except Exception as e:
        print(f"[GSC] ⚠️ Lấy dữ liệu theo trang lỗi ({type(e).__name__}: {str(e)[:100]})"
              " — vẫn lưu snapshot query; --gsc kế tiếp tự thử lại.")

    today = date.today().isoformat()
    save_snapshot(rows, (date.today() - timedelta(days=days - 1)).isoformat(), today,
                  pages=pages)
    mark_fetch_run()
    print()
    print_report()
    from utils.alerts import hint_pending
    hint_pending()   # rank history chưa đổi → chỉ nhắc, không gửi trùng


def run_keyword_suggest_cli(limit: int = None) -> int:
    """In danh sách query chưa theo dõi đủ ngưỡng impressions. Trả exit code."""
    rows = latest_gsc_rows()
    if not rows:
        print("[Keyword] Chưa có dữ liệu Search Console — lấy trước: python main.py --gsc")
        return 0

    from utils.keywords import load_keywords
    tracked = load_keywords()
    min_imps = getattr(cfg, "KEYWORD_SUGGEST_MIN_IMPRESSIONS", 30)
    items = suggest_keywords(rows, tracked, min_impressions=min_imps,
                             limit=limit or getattr(cfg, "KEYWORD_SUGGEST_LIMIT", 20))
    print("=" * 92)
    print(f"  TỪ KHÓA ĐỀ XUẤT TỪ SEARCH CONSOLE — {getattr(cfg, 'GSC_SITE_URL', '?')}")
    print(f"  Query chưa theo dõi, impressions ≥ {min_imps} "
          f"(đang track {len(tracked)} từ khóa | snapshot mới nhất)")
    print("=" * 92)
    if not items:
        print("  Không còn query nào đủ ngưỡng. Thử hạ KEYWORD_SUGGEST_MIN_IMPRESSIONS trong config/settings.py.")
        return 0

    for i, d in enumerate(items, 1):
        print(f"  {i:>2}. {d['query'][:50]:<50}{d['impressions']:>7} hiện{d['clicks']:>7} clicks"
              f"  (vị trí TB {d['position']:.1f})")
    print("-" * 92)
    print('  Thêm vào theo dõi:  python main.py --gsc-add-keyword "nguyên văn query"')
    print("  Xếp hạng của từ khóa mới sẽ xuất hiện ở lần check kế tiếp: python main.py --rank")
    return 0


def run_add_keyword_cli(keyword: str, assume_yes: bool = False) -> int:
    """Thêm một từ khóa vào config/keywords.json (có bước xác nhận).

    Exit code: 0 đã thêm | 1 người dùng hủy hoặc trùng | 2 thiếu tham số.
    """
    keyword = " ".join((keyword or "").strip().split())
    if not keyword:
        print('[Keyword] ⚠️ Thiếu từ khóa — dùng: python main.py --gsc-add-keyword "nối mi quận 7"')
        return 2

    if not assume_yes:
        try:
            ans = input(f"[Keyword] Thêm '{keyword}' vào danh sách theo dõi? [Y/n] ").strip().lower()
        except EOFError:
            ans = "n"
        if ans not in ("", "y", "yes", "d", "đ"):
            print("[Keyword] Đã hủy — không ghi gì vào config/keywords.json.")
            return 1

    from utils.keywords import add_keyword
    added, msg = add_keyword(keyword)
    print(f"[Keyword] {'✅' if added else '⚠️'} {msg}")
    return 0 if added else 1
