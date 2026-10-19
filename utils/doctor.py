# -*- coding: utf-8 -*-
"""
utils/doctor.py — Combo #1: `python main.py --doctor` — kiểm tra môi trường
1 lệnh, phục vụ docs/CHECKLIST_FIRST_RUN.md.

Mỗi check là (tên, trạng thái, dòng hướng dẫn sửa nếu ✗). TRẠNG THÁI:
 ✓ = sẵn sàng dùng được;   ! = có dữ liệu nhưng có điểm cần lưu ý;
 ✗ = thiếu/hỏng — đi kèm dòng "sửa: ...". Không bao giờ raise; dữ liệu hỏng
 coi như thiếu. KHÔNG in token/mật khẩu (chỉ in "đã điền (…xyz)" 4 ký tự cuối).

Kiểm tra thuần file/config là KHÔNG mạng; check CÓ mạng duy nhất là Ollama
(GET /api/tags) và chỉ chạy khi truyền --net. Mặc định `--doctor` an toàn
chạy mọi lúc, không gửi request nào.
"""
import json
import os
import subprocess
from datetime import datetime, timedelta

import config.settings as cfg
from utils import site_paths

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

OK_MARK = "✓"
WARN_MARK = "!"
BAD_MARK = "✗"


def _mask(secret: str) -> str:
    s = (secret or "").strip()
    return f"đã điền (…{s[-4:]})" if len(s) > 8 else "đã điền"


def _file_age_days(path: str):
    """Số ngày kể từ lần ghi gần nhất, hoặc None khi file không tồn tại."""
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return None
    return (datetime.now() - datetime.fromtimestamp(mtime)).days


def _load_json(path: str):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# ─── từng check: trả (status, detail) — status "ok"/"warn"/"bad" ─────────────

def check_target_url():
    dom = site_paths.site_domain()
    if dom:
        return "ok", f"TARGET_URL → {dom} ({cfg.TARGET_URL})"
    return "bad", "TARGET_URL để trống — sửa config/settings.py PHẦN đầu file."


def check_keywords():
    from utils.keywords import load_keywords
    kws = load_keywords()
    if kws:
        return "ok" if len(kws) >= 3 else "warn", \
            f"config/keywords.json có {len(kws)} từ khóa ({', '.join(kws[:3])}…)"
    return "bad", "Chưa có từ khóa nào — điền config/keywords.json (schema {\"site\", \"keywords\"})."


def check_rank_history():
    from utils.rank_tracker import _history_path
    path = _history_path()
    age = _file_age_days(path)
    if age is None:
        return "warn", ("Chưa check xếp hạng lần nào — lệnh: python main.py --rank "
                        "(cần Playwright + fingerprint theo docs/CHECKLIST_FIRST_RUN.md)")
    if age > 7:
        return "warn", f"Lịch sử xếp hạng cũ {age} ngày ({os.path.basename(path)}) — nên chạy --rank."
    data = _load_json(path) or {}
    n_checks = len(data.get("checks") or {})
    return "ok", f"Lịch sử xếp hạng mới ({age} ngày trước, {n_checks} lần check)."


def check_gsc():
    path = site_paths.per_site("gsc_history.json",
                               os.path.join(ROOT, "data"))
    data = _load_json(path)
    if isinstance(data, dict) and data.get("snapshots"):
        snaps = data["snapshots"]
        if isinstance(snaps, dict) and snaps:
            latest = sorted(snaps.keys())[-1]
            return "ok", f"GSC có dữ liệu (fetch mới nhất: {latest[:19]})."
    cred = os.path.join(ROOT, "config", "gsc_service_account.json")
    if os.path.isfile(cred):
        return "warn", ("Credential GSC có nhưng CHƯA fetch lần nào — "
                        "python main.py --gsc (xem docs/SETUP_GSC.md, property phải trùng domain).")
    return "bad", ("Chưa có gì của GSC — tạo service account + key rồi đặt "
                   "config/gsc_service_account.json (docs/SETUP_GSC.md).")


def check_alerts():
    if not bool(getattr(cfg, "ALERTS_ENABLE", False)):
        return "warn", ("Cảnh báo TẮT (ALERTS_ENABLE=False) — chỉ in console. "
                        "Bật Telegram: docs/SETUP_ALERTS.md (~5 phút).")
    token = os.getenv("TELEGRAM_BOT_TOKEN") or str(cfg.TELEGRAM_BOT_TOKEN or "")
    chat = os.getenv("TELEGRAM_CHAT_ID") or str(cfg.TELEGRAM_CHAT_ID or "")
    if token and chat:
        return "ok", f"Telegram cấu hình xong (token {_mask(token)}, chat {chat[-4:]})."
    return "bad", ("ALERTS_ENABLE=True nhưng thiếu token/chat — env TELEGRAM_BOT_TOKEN "
                   "+ TELEGRAM_CHAT_ID (docs/SETUP_ALERTS.md).")


def check_ollama_config():
    url = str(getattr(cfg, "OLLAMA_URL", "") or "")
    model = str(getattr(cfg, "CONTENT_MODEL", "") or "")
    if not url or not model:
        return "bad", "OLLAMA_URL hoặc CONTENT_MODEL để trống (settings PHẦN C?)."
    return "ok", f"Config Ollama: {url} (model {model}) — quyền kiểm server bằng --doctor --net."


def check_ollama_live():
    """Check CÓ mạng — chỉ chạy khi --net."""
    import utils.ollama_client as oc
    info = oc.check_connection()
    if info["ok"]:
        models = info.get("models") or []
        model = str(cfg.CONTENT_MODEL)
        if model in models:
            return "ok", f"Ollama sống, model {model} có sẵn."
        return "warn", f"Ollama sống nhưng thiếu model {model} — ollama pull {model}."
    return "bad", info.get("message", "Ollama không trả lời.")


def check_wordpress():
    url = str(getattr(cfg, "WP_URL", "") or "")
    user = str(getattr(cfg, "WP_USER", "") or "")
    password = os.getenv("WP_APP_PASSWORD") or str(getattr(cfg, "WP_APP_PASSWORD", "") or "")
    if url and user and password:
        return "ok", f"WordPress cấu hình xong ({url}, user {user}, pass {_mask(password)})."
    if url or user or password:
        return "warn", "WP cấu hình chưa đủ 1 trong 3 — đẩy nháp vẫn báo thiếu rõ ràng khi chạy."
    return "warn", ("WP chưa cấu hình (PHẦN L) — --wp-push sẽ hướng dẫn khi chạy. "
                    "App Password: WP admin → Profile → Application Passwords.")


def check_backlinks():
    from utils.backlinks import _state_path  # noqa: F401  (chỉ kiểm tồn tại file store)
    store = site_paths.per_site(getattr(cfg, "BACKLINK_STORE_FILE", "backlinks.json"),
                                os.path.join(ROOT, "config"))
    data = _load_json(store)
    if isinstance(data, dict) and data.get("links"):
        return "ok", f"backlinks.json có {len(data['links'])} link đang theo dõi."
    return "warn", ("Chưa có backlink nào trong config/backlinks.json — thêm vào sau khi "
                    "đặt link đầu tiên: --backlink-add hoặc CSV từ GSC (--backlink-import).")


def check_drafts():
    d = os.path.join(ROOT, str(getattr(cfg, "CONTENT_DRAFTS_DIR", "content/drafts")
                               ).replace("/", os.sep))
    try:
        files = [f for f in os.listdir(d) if f.endswith(".md")]
    except OSError:
        files = []
    if files:
        return "ok", f"{len(files)} bản nháp trong {os.path.relpath(d, ROOT)} — mới nhất: {sorted(files)[-1][:40]}"
    return "warn", "Chưa có bản nháp nào — python main.py --generate \"từ khóa\" (cần Ollama)."


def check_state_dir():
    if site_paths.is_multi_site():
        slug = site_paths.site_slug()
        return "ok", f"Multi-site BẬT → dữ liệu ở data/{slug}/ (các file đề cập trên nằm trong đó)."
    return "ok", "Đơn site: dữ liệu phẳng ở gốc (data/ + config/) — như mặc định."


def _schtasks_registered(name: str) -> bool:
    """Windows: `schtasks /Query /TN name` vừa query vừa returncode 0 = đã đăng ký.
    Nền khác / không chạy được → False (caller tự hiện nhãn an toàn). Chỉ ĐỌC —
    không đăng ký, không sửa task nào."""
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        proc = subprocess.run(["schtasks", "/Query", "/TN", name],
                              capture_output=True, text=True, timeout=10, flags=flags)
        return proc.returncode == 0
    except Exception:
        return False


def check_scheduler():
    """T39 — job scheduler đã đăng ký qua schtasks chưa. Soi tên task đúng cách
    `--scheduler-install` in (SEO-Bot-<Job>-<HHMM>), chỉ query không đụng gì."""
    try:
        from utils.scheduler import JOBS, TASK_PREFIX
    except Exception:
        return "warn", "không kiểm được scheduler (thiếu module) — bỏ qua an toàn."
    expected = []
    for name, job in JOBS.items():
        for hour in job["hours"]:
            hhmm = f"{int(hour):02d}:00"
            expected.append(f"{TASK_PREFIX}-{name.capitalize()}-{hhmm.replace(':', '')}")
    if not expected:
        return "warn", "không job nào có giờ khai báo (JOBS) — --run-job tay vẫn dùng được."
    got = [tn for tn in expected if _schtasks_registered(tn)]
    if not got:
        return "warn", (f"0/{len(expected)} job tự chạy đã đăng ký — chạy --scheduler-install "
                        "(chỉ IN lệnh /Create, bạn tự copy vào Command Prompt).")
    if len(got) < len(expected):
        missing = [tn for tn in expected if tn not in got]
        show = ", ".join(missing[:3]) + ("…" if len(missing) > 3 else "")
        return "warn", (f"{len(got)}/{len(expected)} job đã đăng ký — thiếu {show}; "
                        "chạy lại --scheduler-install lấy lệnh cho job còn thiếu.")
    return "ok", f"{len(got)}/{len(expected)} job tự chạy đã đăng ký (schtasks query thấy đủ)."


def check_indexnow():
    """T39 — IndexNow: key đã submit cho Bing/Yandex chưa (state có ngày 'sent')."""
    try:
        from utils.indexnow import key_state_file
        state = _load_json(key_state_file())
    except Exception as e:
        return "warn", f"không kiểm được IndexNow ({type(e).__name__}) — bỏ qua an toàn."
    sent = (state or {}).get("sent") or {}
    if sent:
        latest = max(sent.keys())
        return "ok", f"IndexNow đã submit ({len(sent)} ngày có gửi, mới nhất {latest})."
    return "warn", ("IndexNow chưa submit lần nào — bài mới để Bing biết nhanh hơn: "
                    "--indexnow-key <key> (key là secret) + upload key file lên site (docs/).")


def check_pagespeed_key():
    """T39 — PageSpeed key là tùy chọn: không key PSI chạy bằng quota ẩn toàn cầu
    (đang cạn — đo 14-10 dính 429); có key thì đo bài T33 chạy ổn định."""
    key = os.getenv("PAGESPEED_API_KEY") or str(getattr(cfg, "PAGESPEED_API_KEY", "") or "")
    if key:
        return "ok", f"PageSpeed API key đã điền ({_mask(key)}) — PSI đo bài không dính quota ẩn."
    return "warn", ("PageSpeed chưa điền key — quota ẩn toàn cầu có thể 429. Tạo key miễn phí "
                    "điền PAGESPEED_API_KEY (key là secret, không in log, không mật).")


# ─── GỘP + IN ────────────────────────────────────────────────────────────────

CHECKS = (("Site & từ khóa", (check_target_url, check_keywords, check_rank_history)),
          ("Search Console", (check_gsc,)),
          ("Cảnh báo Telegram", (check_alerts,)),
          ("Content (Ollama)", (check_ollama_config,)),
          ("Job tự chạy (scheduler)", (check_scheduler,)),
          ("IndexNow", (check_indexnow,)),
          ("PageSpeed", (check_pagespeed_key,)),
          ("Backlink", (check_backlinks,)),
          ("WordPress", (check_wordpress,)),
          ("Bản nháp & site", (check_drafts, check_state_dir)))


def run_checks(net: bool = False) -> list[tuple[str, str, str, str]]:
    """Chạy tất cả check → [(group, name, mark, detail)]. Mỗi check lỗi chỉ nuốt chính nó."""
    out = []
    for group, fns in CHECKS:
        for fn in fns:
            try:
                status, detail = fn()
            except Exception as e:
                status, detail = "warn", f"không kiểm được ({type(e).__name__}) — bỏ qua an toàn"
            out.append((group, fn.__name__.replace("check_", ""),
                        {"ok": OK_MARK, "warn": WARN_MARK, "bad": BAD_MARK}.get(status, WARN_MARK),
                        detail))
    if net:
        try:
            status, detail = check_ollama_live()
        except Exception as e:
            status, detail = "warn", f"không kiểm được ({type(e).__name__}) — bỏ qua an toàn"
        out.append(("Content (Ollama)", "ollama_live",
                    {"ok": OK_MARK, "warn": WARN_MARK, "bad": BAD_MARK}.get(status, WARN_MARK),
                    detail))
    return out


def run_doctor_cli(net: bool = False) -> int:
    """Entry `--doctor`. In bảng + đếm; exit 0 luôn (đây là kiểm tra, không phải test PASSED)."""
    results = run_checks(net=net)
    marks = [m for _, _, m, _ in results]
    print("=" * 78)
    print(f"  KIỂM TRA MÔI TRƯỜNG — python main.py --doctor"
          f"{' (kèm check mạng Ollama)' if net else ' (thêm --net để ping Ollama)'}")
    print(f"  Site: {site_paths.site_domain() or '(chưa cấu hình)'} "
          f"| {site_paths.site_slug() if site_paths.is_multi_site() else 'đơn site'} "
          f"| {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 78)
    group_prev = None
    for group, name, mark, detail in results:
        if group != group_prev:
            print(f"\n[{group}]")
            group_prev = group
        print(f"  {mark} {detail}")
    n_ok, n_warn, n_bad = (marks.count(OK_MARK), marks.count(WARN_MARK), marks.count(BAD_MARK))
    print()
    print("=" * 78)
    if n_bad:
        print(f"  TỔNG: {n_ok} sẵn sàng | {n_warn} cần lưu ý | {n_bad} thiếu — làm theo dòng {BAD_MARK} trước")
    elif n_warn:
        print(f"  TỔNG: {n_ok} sẵn sàng | {n_warn} cần lưu ý | 0 thiếu — dùng được ngay")
    else:
        print(f"  TỔNG: {n_ok} sẵn sàng — mọi thứ cấu hình xong!")
    print("  Lần đầu chạy thật? Xem docs/CHECKLIST_FIRST_RUN.md (thứ tự rẻ → đắt).")
    print("=" * 78)
    return 0
