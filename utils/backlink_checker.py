"""
utils/backlink_checker.py — F7: tầng fetch của backlink check (batch + cache + báo cáo).

Tách lớp rõ: `utils/backlinks.py` trả lời "HTML này có link tới site mình không",
còn file này lo network. Đây là trang của NGƯỜI KHÁC nên luật chơi là lịch sự:
MỘT request cho mỗi URL mỗi đợt, tối đa `BACKLINK_PARALLEL` luồng, timeout
`BACKLINK_TIMEOUT`, không retry để lách 403, không đổi User-Agent, không giải
CAPTCHA, không đụng lớp anti-detect. 403/429/404/timeout là DỮ LIỆU — ghi vào báo
cáo rồi đi tiếp, batch không dừng.

Redirect đi theo thủ công (`default_fetcher`) để soi từng đích trước khi gọi: một
trang bên thứ ba có thể trỏ Location về file:// hay địa chỉ metadata nội bộ.

`requests` import trong hàm (GUI import module này để bật nút, không được kéo theo
network stack). CSV không tự viết ở đây: `check_rows()` đưa (header, rows) cho
`utils/exporter.py` — nơi duy nhất biết `_unique_path` và BOM.
"""
from concurrent.futures import ThreadPoolExecutor
import ipaddress
from urllib.parse import urljoin, urlsplit

import config.settings as cfg
from utils import backlinks as bl

CSV_HEADER = ["trạng thái", "url", "host", "có link", "dofollow", "số link",
              "anchor", "check lúc", "url cuối", "lỗi"]
_ERROR_CLIP = 120
_MAX_REDIRECTS = 5            # trần hop redirect đi theo; hết trần thì dừng, status là dữ liệu


# ─── fetch ───────────────────────────────────────────────────────────────────


def _destination_ok(url: str) -> bool:
    """Đích redirect có được phép gọi không — chỉ http(s) tới host công khai.

    Trang blog là của người khác, nên Location có thể trỏ bất cứ đâu: file://, địa chỉ
    metadata nội bộ của cloud (169.254.169.254), localhost, dải private. Bot không đi
    theo những đích đó chỉ vì một trang bên thứ ba bảo thế.

    Giới hạn có ý thức: chỉ soi phần địa chỉ viết trong Location. Một hostname công
    khai mà DNS trỏ về IP nội bộ vẫn lọt — đây là chặn đúng cái đọc được, không phải
    sandbox. URL gốc owner tự khai trong config/backlinks.json thì không soi (đó là
    lựa chọn của chính owner, và cần cho việc thử ở máy).
    """
    try:
        parts = urlsplit(str(url or "").strip())
    except ValueError:
        return False
    if parts.scheme not in ("http", "https"):
        return False
    host = (parts.hostname or "").strip().lower().strip(".")
    if not host or host == "localhost" or host.endswith(".localhost"):
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return True                      # tên miền → để DNS/requests quyết định
    return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
                or ip.is_multicast or ip.is_unspecified)


def _get(requests, url: str):
    """MỘT request cho một URL, không tự đi theo redirect (để tự soi từng hop)."""
    return requests.get(url, timeout=cfg.BACKLINK_TIMEOUT, allow_redirects=False,
                        headers={"User-Agent": cfg.AUDIT_USER_AGENT})


def default_fetcher(url: str) -> tuple:
    """(status, html, final_url) của MỘT URL — không tự retry.

    Redirect đi theo THỦ CÔNG (`allow_redirects=False` rồi đọc Location) để soi được
    từng đích TRƯỚC khi gọi: để `requests` tự đi thì request tới đích nguy hiểm đã
    xong rồi mới biết nó đi đâu. Gặp đích bị chặn hoặc quá `_MAX_REDIRECTS` hop thì
    dừng lại và trả status của hop cuối — 3xx là DỮ LIỆU cho báo cáo, không phải lỗi.

    404/403 KHÔNG raise: `requests` trả status, và status chính là kết quả owner cần
    thấy. Chỉ lỗi mạng thật (DNS, timeout, connection reset) mới nổi exception —
    `_fetch_one` biến nó thành một dòng báo cáo.
    """
    import requests
    resp = _get(requests, url)
    hops = 0
    while getattr(resp, "is_redirect", False) and hops < _MAX_REDIRECTS:
        nxt = urljoin(resp.url or url, (resp.headers or {}).get("location") or "")
        if not _destination_ok(nxt):
            break
        hops += 1
        resp = _get(requests, nxt)
    return resp.status_code, resp.text or "", resp.url or url


def _clip(text: str) -> str:
    return text if len(text) <= _ERROR_CLIP else text[:_ERROR_CLIP - 1] + "…"


def _pool_size(count: int) -> int:
    """Số luồng thực dùng: không bao giờ vượt BACKLINK_PARALLEL và không spawn thừa."""
    if count <= 0:
        return 0
    try:
        cap = int(getattr(cfg, "BACKLINK_PARALLEL", 5))
    except (TypeError, ValueError):
        cap = 5
    return max(1, min(cap, count))


def _fetch_one(fetcher, url: str, target: str) -> dict:
    try:
        status, html, final_url = fetcher(url)
        error = ""
    except Exception as exc:
        status, html, final_url = 0, "", ""
        error = f"{type(exc).__name__}: {_clip(str(exc))}"
    entry = bl.verify_page(url, html, status, target, final_url=final_url or url)
    entry["error"] = error
    entry["checked_at"] = bl._now()
    return entry


# ─── rows ────────────────────────────────────────────────────────────────────


def _host_of(entry: dict) -> str:
    return bl._norm_domain(entry.get("final_url") or entry.get("url") or "")


def _as_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _status_label(status, error: str) -> str:
    if error:
        return f"Lỗi: {_clip(error)}"
    code = _as_int(status)
    if code == 0:
        return "Không đọc được"
    if 200 <= code < 300:
        return "Còn sống"
    if 300 <= code < 400:
        return f"Chuyển hướng ({code})"
    if code in (401, 403):
        return f"Bị chặn ({code})"
    if code in (404, 410):
        return f"Chết ({code})"
    if 400 <= code < 500:
        return f"Lỗi trang ({code})"
    if code >= 500:
        return f"Trang hỏng ({code})"
    return f"HTTP {code}"


def _row(entry: dict, cached: bool = False) -> dict:
    """Entry (vừa fetch hoặc đọc cache) -> dòng báo cáo, luôn đủ keys cho CSV."""
    safe = entry if isinstance(entry, dict) else {}
    return {"url": str(safe.get("url") or ""),
            "host": _host_of(safe),
            "status": _as_int(safe.get("status")),
            "has_link": bool(safe.get("has_link")),
            "dofollow": bool(safe.get("dofollow")),
            "links_to_target": _as_int(safe.get("links_to_target")),
            "anchors": [str(a) for a in (safe.get("anchors") or []) if str(a)],
            "rel_seen": [str(r) for r in (safe.get("rel_seen") or [])],
            "final_url": str(safe.get("final_url") or safe.get("url") or ""),
            "error": str(safe.get("error") or ""),
            "checked_at": str(safe.get("checked_at") or ""),
            "cached": cached}


def check_rows(rows) -> tuple:
    """(header, list[row]) theo đúng thứ tự cột đã chốt — exporter chỉ việc ghi."""
    data = []
    for row in (rows or []):
        data.append([_status_label(row.get("status"), row.get("error") or ""),
                     row.get("url", ""), row.get("host", ""),
                     "có" if row.get("has_link") else "không",
                     "có" if row.get("dofollow") else "không",
                     str(_as_int(row.get("links_to_target"))),
                     " | ".join(row.get("anchors") or []),
                     row.get("checked_at", ""), row.get("final_url", ""),
                     row.get("error", "")])
    return list(CSV_HEADER), data


# ─── batch check ─────────────────────────────────────────────────────────────


def _problem_rank(row: dict):
    """Link cần xử lý (chết/bị chặn/không link/nofollow) lên đầu, trong nhóm theo URL."""
    clean = (not row["error"]) and row["has_link"] and row["dofollow"]
    return (1 if clean else 0, row["url"])


def state_rows(state: dict) -> tuple:
    """state (chìa _link_key -> entry) -> (header, rows), link có vấn đề lên đầu."""
    rows = sorted((_row(e) for e in state.values()), key=_problem_rank)
    return check_rows(rows)


def check_links(links, state, fetcher=None, refresh: bool = False,
                now=None, domain=None) -> tuple:
    """Check một đợt. Trả (state_mới, rows_theo_thứ_tự_input). Không raise, không dừng."""
    fetcher = fetcher or default_fetcher
    target = bl._norm_domain(bl.target_domain() if domain is None else domain)
    base = state if isinstance(state, dict) else {}

    prepared, seen = [], set()
    for item in (links or []):
        raw = item.get("url") if isinstance(item, dict) else item
        url = bl._valid_url(raw if isinstance(raw, str) else "")
        key = bl._link_key(url)
        if not key or key in seen:
            continue
        seen.add(key)
        prepared.append(url)

    pending = []
    reused = {}
    for url in prepared:
        cached_entry = base.get(bl._link_key(url))
        if not refresh and bl.is_fresh(cached_entry, now=now):
            reused[url] = cached_entry
        else:
            pending.append(url)

    fetched = []
    if pending:
        with ThreadPoolExecutor(max_workers=_pool_size(len(pending))) as pool:
            fetched = list(pool.map(lambda u: _fetch_one(fetcher, u, target), pending))
    for url, entry in zip(pending, fetched):
        reused[url] = entry

    new_state = dict(base)
    rows = []
    for url in prepared:
        entry = reused.get(url) or {}
        cached = url not in pending
        rows.append(_row(entry, cached=cached))
        if not cached:
            new_state[bl._link_key(url)] = entry
    return new_state, rows


# ─── báo cáo + CLI ───────────────────────────────────────────────────────────


def _pct(part: int, whole: int) -> str:
    return f"{round(part / whole * 100, 1)}%" if whole else "—"


def format_report(rows) -> str:
    """Người đọc cần ba số: bao nhiêu link còn sống, còn link tới mình, dofollow mấy cái."""
    rows = list(rows or [])
    total = len(rows)
    alive = sum(1 for r in rows if 200 <= r["status"] < 400)
    linked = sum(1 for r in rows if r["has_link"])
    follow = sum(1 for r in rows if r["has_link"] and r["dofollow"])
    nofollow = linked - follow
    cached = sum(1 for r in rows if r["cached"])
    broken = sum(1 for r in rows if r["error"])

    lines = [f"[Backlink] {total} link: {alive}/{total} còn sống ({_pct(alive, total)}), "
             f"{linked}/{total} còn link tới site ({_pct(linked, total)}), "
             f"{follow}/{linked} dofollow ({_pct(follow, linked)})"]
    if nofollow:
        lines.append(f"[Backlink] ⚠️ {nofollow} link chỉ có nofollow/sponsored/ugc — "
                     "không chuyển uy tín, cần đổi hoặc đặt chỗ khác")
    if broken:
        lines.append(f"[Backlink] ⚠️ {broken} link không đọc được (mạng/chặn) — "
                     "đó là lỗi FETCH, chưa kết luận link chết")
    if cached:
        lines.append(f"[Backlink] ℹ️ {cached} link dùng cache trong "
                     f"{cfg.BACKLINK_CACHE_HOURS}h — --backlink-refresh để check lại")

    for row in rows:
        mark = "✅" if row["has_link"] and row["dofollow"] else ("🟡" if row["has_link"] else "❌")
        detail = _status_label(row["status"], row["error"])
        if row["has_link"]:
            rel = "dofollow" if row["dofollow"] else "nofollow"
            anchor = f" — anchor: “{row['anchors'][0]}”" if row["anchors"] else ""
            detail = f"{detail}, {rel}, {row['links_to_target']} link{anchor}"
        lines.append(f"  {mark} {row['url']}  [{detail}]")
    return "\n".join(lines)


def run_backlink_check_cli(limit=None, refresh: bool = False, url: str = "",
                           fetcher=None) -> int:
    """`python main.py --backlink-check` — trả mã exit, không tự sys.exit."""
    all_links = bl.load_links()
    links = all_links
    if url:
        want = bl._link_key(url)
        links = [l for l in all_links if bl._link_key(l["url"]) == want]
        if not links:
            print(f"[Backlink] '{url}' không có trong danh sách — thêm trước: "
                  f'python main.py --backlink-add "{url}"')
            return 2

    if not links:
        print('[Backlink] Danh sách backlink đang trống — thêm link bạn đã thật sự đặt:')
        print('  python main.py --backlink-add "https://site-nguoi-khac/bai-co-link-cua-ban"')
        print("  hoặc import CSV 'External links' tải tay từ Search Console:")
        print("  python main.py --backlink-import <duong-dan.csv>")
        return 2

    total = len(links)
    left = 0
    try:
        cap = int(limit) if limit is not None else 0
    except (TypeError, ValueError):
        cap = 0
    if 0 < cap < total:
        left = total - cap
        links = links[:cap]

    target = bl.target_domain()
    print(f"[Backlink] Kiểm tra {len(links)} link tới “{target}” — "
          f"tối đa {cfg.BACKLINK_PARALLEL} luồng, timeout {cfg.BACKLINK_TIMEOUT}s/link")

    state = bl.load_state()
    known = {bl._link_key(l["url"]) for l in all_links}
    # Ảnh state lần trước CHỈ gồm link vẫn có trong danh sách — link owner gỡ
    # khỏi danh sách không phải "mất backlink", không tạo cảnh báo.
    prev_state = {k: v for k, v in state.items() if k in known}
    new_state, rows = check_links(links, state, fetcher=fetcher, refresh=refresh,
                                  domain=target)
    bl.save_state({k: v for k, v in new_state.items() if k in known})

    # Cảnh báo mất backlink (G-2): so state vừa ghi với lần trước — chạy SAU
    # khi đã lưu, tự nuốt lỗi, kết quả check không chết theo bộ cảnh báo.
    try:
        from utils.backlink_alerts import check_and_notify
        check_and_notify(prev_state,
                         {k: v for k, v in new_state.items() if k in known},
                         domain=target)
    except Exception:
        pass

    print(format_report(rows))
    if left:
        print(f"[Backlink] ⏭️ còn {left} link chưa check trong đợt này — chạy lại "
              "không có --backlink-limit để xem tiếp (link đã check thì dùng cache)")
    print("[Backlink] 💾 Đã lưu kết quả — mở bằng Excel: python main.py --export backlinks")
    return 0


def run_backlink_add_cli(url: str, note: str = "") -> int:
    """`--backlink-add "URL"` — thêm một link đã thật sự đặt vào danh sách theo dõi."""
    ok, msg = bl.add_link(url, note=note)
    print(f"[Backlink] {'✅' if ok else '⚠️'} {msg}")
    if ok:
        print("[Backlink] Check ngay: python main.py --backlink-check")
    return 0 if ok else 2


def run_backlink_import_cli(path: str) -> int:
    """`--backlink-import <file.csv>` — nạp CSV "External links" tải tay từ Search Console."""
    added, msg = bl.import_gsc_csv(path)
    # message mở đầu bằng "Đã thêm" = file đọc được và nhận ra URL, kể cả khi cả thảy
    # đã có trong danh sách (không phải lỗi); còn lại là file thiếu/hổng/không có URL.
    ok = msg.startswith("Đã thêm")
    print(f"[Backlink] {'✅' if ok else '⚠️'} {msg}")
    if ok and added:
        print("[Backlink] Check ngay: python main.py --backlink-check")
    return 0 if ok else 2
