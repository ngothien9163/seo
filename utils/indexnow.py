"""
utils/indexnow.py — T18: đẩy URL vừa mới đăng/cập nhật lên indexnow.org
(Bing/Yandex/Seznam/Naver và mọi engine tham gia tự share cho nhau).

Đây là hướng "Bing WMT" chốt trong brainstorm (D) nhưng KHÔNG dùng Bing API key:
IndexNow là tiêu chuẩn mở — chỉ cần một key hex 8-128 ký tự mình tự sinh + file
key.txt trễ trên site để engine verify. Không có OAuth, không phụ thuộc key bên
thứ ba, không thêm dependency (chỉ requests vốn đã có).

Vòng làm việc:
    python main.py --indexnow-key              # sinh key + ghi data/indexnow_key.txt
    #  → (một lần) tải file đó lên site: cùng host với URL sẽ submit
    python main.py --indexnow                  # submit sitemap URLs (default)
    python main.py --indexnow URL1 URL2 ...    # submit các URL chỉ định
    python main.py --indexnow --dry-run        # xem sẽ submit gì + hướng dẫn setup key

Chỉ số một lần/ngày: state data/indexnow_state.json ghi "YYYY-MM-DD" thì sẽ
chỉ chạy khi khởi tạo; đánh dấu CHỈ KHI submit thành công — mạng hỏng để lần
kế test lại. Ghi atomic (tmp + os.replace) như các state khác.

KHÔNG có request tự động nào hợp lệ trừ khi key file đã đi lên site: engine trả
403 (key not valid) — CLI in nhãn rõ "file key chưa lên site" bằng ngôn ngữ
hướng dẫn, không crash, không retry loop.
"""
import json
import os
import sys
import time
import secrets
import urllib.parse
from datetime import datetime

import requests

import config.settings as cfg
from utils import site_paths

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Endpoint indexnow.org chính thức — engine nào tham gia cũng đều nhận qua đây.
INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"

# Giới hạn mỗi POST theo spec indexnow.org: mỗi lượt tối đa 10,000 URL.
MAX_URLS_PER_POST = 10000

__all__ = ["generate_key", "read_key", "key_file_path", "submit_urls",
           "collect_target_urls", "discover_urls", "known_seed", "mark_known",
           "run_indexnow_cli", "run_indexnow_key_cli"]


# ─── KEY: sinh + lưu + đọc ──────────────────────────────────────────────────

def key_file_path() -> str:
    """File key per-site trong data/ — chỉ cần nội dung cần tải lên site của bạn."""
    return site_paths.site_file("indexnow_key.txt")


def key_state_file() -> str:
    return site_paths.site_file("indexnow_state.json")


def generate_key() -> str:
    """Key hex ngẫu nhiên 32 ký tự hợp lệ theo spec indexnow (8-128, [0-9a-f])."""
    return secrets.token_hex(16)


def read_key() -> str | None:
    """Key đã sinh nếu có — file mất/hỏng → None (CLI sẽ hướng chạy --indexnow-key)."""
    path = key_file_path()
    try:
        return open(path, encoding="utf-8").read().strip() or None
    except OSError:
        return None


def save_key(key: str) -> str:
    """Ghi key vào file per-site (atomic) — trả key."""
    path = key_file_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(key)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
    return key


# ─── STATE: 1 lần/ngày chống nhồi đúng X-Max của indexnow ──────────────────

def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def sent_today(day: str = "") -> bool:
    """Hôm nay đã submit thành công chưa (key state ngày 'YYYY-MM-DD')."""
    try:
        with open(key_state_file(), encoding="utf-8") as f:
            state = json.load(f)
        return (day or today_str()) in state.get("sent", {})
    except Exception:
        return False               # file thiếu/hỏng → coi như chưa gửi


def mark_sent(day: str = "") -> None:
    day = day or today_str()
    path = key_state_file()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    try:
        with open(path, encoding="utf-8") as f:
            state = json.load(f)
        if not isinstance(state, dict) or not isinstance(state.get("sent"), dict):
            state = {"sent": {}}
    except Exception:
        state = {"sent": {}}
    state["sent"][day] = {
        "at": datetime.now().isoformat(timespec="seconds"),
    }
    # giữ tối đa 60 ngày gần nhất — state nhỏ chỉ cần nhớ gần
    keep = sorted(state["sent"], reverse=True)[:60]
    state["sent"] = {k: state["sent"][k] for k in keep}
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


# ─── SUBMIT: gọi API indexnow.org ───────────────────────────────────────────

def submit_urls(urls: list, key: str, dry_run: bool = False):
    """Submit 1 lượt (POST JSON với host + key + urlList). Trả (ok, code, message).

    - ok=False > không mark_sent — lần chạy kế thử lại.
    - dry_run=True: không gọi mạng, chỉ trả (True, 0, đưa những URLs sẽ submit).
    - trước khi gửi LOẠI URLs không cùng host với key site tránh 422 URL-not-belonging.
    """
    urls = [u.strip() for u in urls if u and u.strip()]
    if not urls:
        return False, 0, "Không có URL nào để submit."

    domain = site_paths.site_domain()
    same_host = [u for u in urls
                 if (urllib.parse.urlparse(u).netloc or "").lower().replace("www.", "")
                 == (domain or "").lower()]
    skipped = len(urls) - len(same_host)
    if not same_host:
        return False, 0, (f"Không còn URL nào cùng host {domain}. "
                          f"URL lạ bị bỏ nếu URL không thuộc site.")
    if dry_run:
        note = f"Dry-run — sẽ submit {len(same_host)} URL tới {INDEXNOW_ENDPOINT}"
        if skipped:
            note += f" (bỏ {skipped} URL lạ host)"
        return True, 0, note + ": " + "; ".join(same_host[:5]) + ("…" if len(same_host) > 5 else "")

    body = {
        "host": domain,
        "key": key,
        "keyLocation": urllib.parse.urljoin(f"https://{domain}/",
                                            os.path.basename(key_file_path())),
        "urlList": same_host[:MAX_URLS_PER_POST],
    }
    try:
        resp = requests.post(INDEXNOW_ENDPOINT, json=body, timeout=30,
                             headers={"Content-Type": "application/json; charset=utf-8"})
        code = resp.status_code
    except requests.exceptions.RequestException as e:
        return False, 0, f"Lỗi mạng: {type(e).__name__}: {e}"

    if code in (200, 202):
        msg = "Đã submit thành công (hoặc engine đang verify key — 202)."
        if code == 202:
            msg = "Engine đã nhận nhưng còn verify key file — kiểm tra file key.txt đã lên site chưa."
        return True, code, msg
    messages = {
        400: "Yêu cầu sai định dạng — key/URL có vấn đề (kiểm tra data/indexnow_key.txt).",
        403: "Key chưa hợp lệ — file indexnow_key.txt chưa được treo trên site (đúng nội dung).",
        422: "URL không thuộc host của key, hoặc key sai chuẩn hex.",
        429: "Too Many Requests — spam guard engine tự chặn, thử lại ngày mai.",
    }
    return False, code, messages.get(code, f"Lỗi không rõ mã {code}: {resp.text[:200]}")


# ─── T24: SITEMAP — đọc URL mới từ sitemap của site, chỉ submit URL chưa biết ──
#
# T18 submit tub audit crawl / rank history; T24 không cần audit trước: tự GET
# sitemap.xml của site (robots khai Sitemap: trước, thiếu thì /sitemap.xml;
# <sitemapindex> đọc từng file con tối đa SITEMAP_INDEX_MAX như auditor). Khác
# known-set (audit + rank history + lần submit trước, state "known") → chỉ mỗi
# URL MỚI được đẩy đi — reindex hàng loạt khi muốn thì --indexnow-full.

SITEMAP_ROBOTS_TRY = 3        # robots khai nhiều Sitemap: thì đọc tối đa 3 file đầu
KNOWN_KEEP = 5000             # state "known" nhớ tối đa N URL — đủ cho site thường

def _sa():
    """import site_auditor lười — dùng mắt xích có sẵn chứ không copy regex/policy."""
    from utils import site_auditor as sa
    return sa


def discover_urls(fetcher=None) -> tuple:
    """(urls, info) — URL trang trong sitemap của site. Tối đa 1 (robots) + 3
    (Sitemap: khai) + 10 (file con) request, chỉ GET file XML — không crawl trang.

    - info: {status, files, count, truncated} để CLI in 1 dòng tường minh.
    - Cùng host + robots cho phép mới nhận (auditor áp cùng luật cho sitemap).
    - Domain chưa cấu hình → ([], info).
    """
    sa = _sa()
    info = {"status": None, "files": [], "count": 0, "truncated": False}
    domain = site_paths.site_domain()
    if not domain:
        return [], info
    fetcher = fetcher or sa._default_fetcher
    root = f"https://{domain}"
    rstatus, robots_text, _ = fetcher(root + "/robots.txt")
    policy = sa.RobotsPolicy(robots_text if rstatus == 200 else "", sa._user_agent())

    sitemaps: list[str] = []
    my_host = domain.lower().replace("www.", "")
    for line in (robots_text or "").splitlines():
        if rstatus == 200 and line.lower().startswith("sitemap:"):
            loc = line.split(":", 1)[1].strip()
            host = (urllib.parse.urlsplit(loc).netloc or "").lower().replace("www.", "")
            if host == my_host:
                sitemaps.append(loc)
    if not sitemaps:
        sitemaps = [root + "/sitemap.xml"]

    urls: list[str] = []
    files: list[str] = []
    for sm in sitemaps[:SITEMAP_ROBOTS_TRY]:
        if sm in files or not policy.allowed(sm):
            continue
        status, body, _ = fetcher(sm)
        info["status"] = status
        if status != 200 or not (body or "").strip():
            continue
        files.append(sm)
        locs = [sa.normalize_url(loc, sm) for loc in sa._LOC_RE.findall(body)]
        index_like = bool(sa._SITEMAP_INDEX_RE.search(body))
        subs = [loc for loc in locs if loc and sa._is_sitemap_file(loc)][:sa.SITEMAP_INDEX_MAX]
        # index XML có nhiều file con hơn SITEMAP_INDEX_MAX → các file sau bị bỏ
        info["truncated"] = info["truncated"] or (
            index_like and len([loc for loc in locs if loc and sa._is_sitemap_file(loc)])
            > sa.SITEMAP_INDEX_MAX)
        sources = subs if index_like else [sm]
        for src in sources:
            text = body if src == sm else ""
            if src != sm:
                if src in files or not policy.allowed(src):
                    continue
                sub_status, sub_body, _ = fetcher(src)
                if sub_status != 200:
                    continue
                files.append(src)
                text = sub_body or ""
            for loc in sa._LOC_RE.findall(text):
                target = sa.normalize_url(loc, src)
                if (target and target not in urls and not sa._is_sitemap_file(target)
                        and sa.same_host(target, root + "/") and policy.allowed(target)):
                    urls.append(target)
        if len(urls) >= MAX_URLS_PER_POST:
            break
    info["files"] = files
    info["count"] = min(len(urls), MAX_URLS_PER_POST)
    return urls[:MAX_URLS_PER_POST], info


def known_seed() -> set:
    """URL đã 'biết trạng thái' của các URL trước đó: state "known" trước + audit
    gần nhất + rank history + trang chủ. Tất cả nguồn đều lười import — hỏng
    nguồn nào bỏ nguồn đó (không submit được sitemap), không raise."""
    out: set[str] = set()
    try:
        with open(key_state_file(), encoding="utf-8") as f:
            state = json.load(f)
        urls = state.get("known") if isinstance(state, dict) else None
        if isinstance(urls, list):
            out.update(str(u) for u in urls if u)
    except Exception:
        pass
    try:
        from utils.site_auditor import load_last_audit
        for f in load_last_audit():
            u = (f.get("url") or "").strip()
            if u:
                out.add(u)
    except Exception:
        pass
    try:
        from utils.rank_tracker import _load_history
        # shape thật: {checks: {timestamp: {keyword: {"url": ..., "top_urls": [...]}}}}
        for kw_result in (_load_history().get("checks") or {}).values():
            if not isinstance(kw_result, dict):
                continue
            for info in kw_result.values():
                if not isinstance(info, dict):
                    continue
                u = (info.get("url") or "").strip()
                if u:
                    out.add(u)
                for u2 in (info.get("top_urls") or []):
                    u2 = (str(u2) or "").strip()
                    if u2:
                        out.add(u2)
    except Exception:
        pass
    if getattr(cfg, "TARGET_URL", ""):
        out.add(cfg.TARGET_URL.rstrip("/") + "/")
    return out


def mark_known(urls: list) -> None:
    """Nhớ URL vừa submit thành công vào state "known" (list, atomic, KNOWN_KEEP)."""
    fresh = [(u or "").strip() for u in urls if (u or "").strip()]
    if not fresh:
        return
    path = key_state_file()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    try:
        with open(path, encoding="utf-8") as f:
            state = json.load(f)
        if not isinstance(state, dict):
            state = {}
    except Exception:
        state = {}
    state.setdefault("sent", {})
    if not isinstance(state["sent"], dict):
        state["sent"] = {}
    merged = [u for u in state.get("known", []) if isinstance(u, str)]
    seen = set(merged)
    for u in fresh:
        if u not in seen:
            seen.add(u)
            merged.append(u)
    state["known"] = merged[-KNOWN_KEEP:]
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


# ─── COLLECT URLs: audit crawl (sitemap thật) + rank history + fallback chủ ─

def collect_target_urls() -> list:
    """Danh sách URL dự kiến submit — nguồn ưu tiên:
    1. URL auditor đã crawl (load_last_audit — findings có đủ mọi trang lỗi, schema
       thật là dict {url, findings} nên đi qua findings chứ không 'pages');
    2. URLs rank history đã lưu (trang đang theo dõi);
    3. fallback TARGET_URL gốc để ít nhất submit trang chủ.
    """
    urls: list[str] = []

    def _push(u):
        u = (u or "").strip()
        if u and u not in seen:
            seen.add(u)
            out.append(u)

    seen: set = set()
    out: list[str] = []
    try:
        from utils.site_auditor import load_last_audit
        for f in load_last_audit():
            _push(f.get("url"))
    except Exception:
        pass
    if not out:
        try:
            from utils.rank_tracker import _load_history
            for rec in _load_history().get("records", []):
                _push((rec.get("url") or "").strip())
        except Exception:
            pass
    if not out:
        _push((getattr(cfg, "TARGET_URL", "") or "").rstrip("/") + "/")
    return out[:MAX_URLS_PER_POST]


# ─── KEY CLI ────────────────────────────────────────────────────────────────

def run_indexnow_key_cli() -> int:
    """--indexnow-key: sinh key lần đầu (hoặc in lại key + hướng dẫn treo file)."""
    key = read_key()
    domain = site_paths.site_domain() or "(chưa cấu hình TARGET_URL)"
    if not key:
        key = save_key(generate_key())
        print(f"[IndexNow] Đã sinh key và ghi vào {key_file_path()}")
    else:
        print(f"[IndexNow] Key hiện có ở {key_file_path()}")
    print(f"[IndexNow] Key : {key}")
    print(f"[IndexNow] Host: {domain}")
    print(f"[IndexNow] Tải file {os.path.basename(key_file_path())} LÊN SITE — 1 trong 2 cách:")
    print('  (1) SFTP/cPanel: đặt ở gốc site thành "indexnow-key.txt" (nội dung = key trên).')
    print('  (2) WP Admin → Media → Add New → upload file này.')
    print('[IndexNow] Sau khi treo xong, chạy: python main.py --indexnow')
    return 0


# ─── SUBMIT CLI ─────────────────────────────────────────────────────────────

def run_indexnow_cli() -> int:
    """Entry --indexnow: 1 lần/ngày + chỉ submit URLs cùng host key.

    T24 — không URL chỉ định:
    - mặc định đọc sitemap của site (1 robots + vài XML request), đóng với
      known-set (state "known" + audit + rank history + trang chủ) → chỉ submit
      URL MỚI; sitemap lỗi/hỏng → fallback collect_target_urls() như T18.
    - --indexnow-full: submit toàn bộ URL trong sitemap bất kể đã biết (nhưng
      vẫn tôn trọng 1 lần/ngày trừ --force).
    Có URL chỉ định (positional) → hành vi T18 nguyên vẹn, không đụng sitemap.
    """
    urls_arg = []
    for arg in sys.argv[sys.argv.index("--indexnow") + 1:] if "--indexnow" in sys.argv else []:
        if arg.startswith("-"):
            break
        urls_arg.append(arg)
    dry = "--dry-run" in sys.argv
    force = "--force" in sys.argv
    full = "--indexnow-full" in sys.argv
    sm_urls: list = []
    sm_info: dict = {}

    key = read_key()
    domain = site_paths.site_domain()
    if not key and not dry:
        print("[IndexNow] Chưa có key — chạy python main.py --indexnow-key trước, "
              "treo file lên site rồi mới submit.")
        return 2
    if not domain:
        print("[IndexNow] Chưa cấu hình TARGET_URL — sửa config/settings.py.")
        return 2

    if urls_arg:
        # URL chỉ định tay → T18 nguyên vẹn (không sitemap, không known diff)
        urls = urls_arg
    else:
        sm_urls, sm_info = discover_urls()
        if not sm_urls or not sm_info.get("files"):
            if sm_info.get("status") is not None and not sm_info.get("files"):
                print(f"[IndexNow] Sitemap HTTP {sm_info['status']} — không đọc được "
                      f"URL nào từ sitemap. Dùng nguồn cũ (audit/rank history) thay.")
            else:
                print("[IndexNow] Không có URL nào trong sitemap (hoặc sitemap lỗi) "
                      "— dùng ngược lại nguồn audit/rank history.")
            urls = collect_target_urls()
        else:
            n_locs = len(sm_info["files"])
            trunc = (" (sitemap index có nhiều file con hơn max — 1 phần)" if sm_info.get("truncated") else "")
            src_note = f"sitemap {n_locs} file XML{trunc}"
            if full:
                urls = sm_urls
            else:
                known_exact = known_seed()
                known_fold = {k.rstrip("/") for k in known_exact}
                urls = [u for u in sm_urls
                        if u not in known_exact and u not in known_fold]
                if not urls:
                    print(f"[IndexNow] {src_note}: {len(sm_urls)} URL — không có URL nào "
                          f"MỚI hơn audit/rank history/lần submit trước → không submit gì. "
                          "Đẩy lại toàn bộ sitemap: --indexnow-full "
                          "(hoặc --indexnow URL1 URL2 ... chỉ định tay).")
                    return 0
            if dry:
                print(f"[IndexNow] {src_note}: {len(sm_urls)} URL — "
                      f"{'sẽ submit toàn bộ (chế độ --indexnow-full)' if full else f'{len(urls)} URL MỚI sẽ submit'}.")

    if not urls:
        print("[IndexNow] Không tìm thấy URL nào (sitemap chưa crawl hoặc TARGET_URL rỗng).")
        return 2

    if dry:
        _, _, dmsg = submit_urls(urls, key=key or "(chưa sinh — chạy --indexnow-key)", dry_run=True)
        print(f"[IndexNow] {dmsg}")
        if not key:
            print("[IndexNow] Chưa có key — chạy python main.py --indexnow-key, "
                  "treo file lên site rồi mới submit thật.")
        return 0

    if not force and sent_today():
        print(f"[IndexNow] Hôm nay đã submit rồi (1 lần/ngày chống spam). "
              "Xem lại URLs cho vui: python main.py --indexnow --dry-run "
              "hoặc gửi ngay lần nữa: --force")
        return 0

    ok, code, msg = submit_urls(urls, key=key)
    if ok:
        mark_sent()
        mark_known(urls)  # sitemap lần sau không submit lại chính những URL này
        print(f"[IndexNow] {msg} — HTTP {code}, {len(urls)} URL cho {domain}. "
              "Chỉ số có thể mất vài giờ — kiểm tra bằng Bing Webmaster sau.")
        return 0
    print(f"[IndexNow] Chưa submit được (HTTP {code}): {msg} "
          "— lần chạy kế tự thử lại khi file key đúng đã ở trên site.")
    return 1
