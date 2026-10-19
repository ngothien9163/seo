"""
utils/scheduler.py — F4: để lịch tự động chạy mà không cần mở GUI.

Đồng hồ thật là Windows Task Scheduler (quyết định đã duyệt ở spec F4): nó gọi

    python main.py --run-job rank      # 07:00 / 13:00 / 19:00
    python main.py --run-job gsc       # 09:00

Module này KHÔNG tự đếm giới hạn ngày và KHÔNG tự thức khuya: nó chỉ
1. chặn hai job chồng nhau (lock tạo bằng O_EXCL, theo PID + heartbeat),
2. hỏi đúng hàm guard của module gốc (can_run_check / can_run_fetch / can_run_session),
3. ghi lại dấu vết vào data/scheduler_state.json để CLI --scheduler-status và GUI đọc.

Spec: docs/superpowers/specs/2026-10-13-f4-scheduler-design.md
Lịch đặt trên Windows: docs/SETUP_SCHEDULER.md
"""
import json
import os
import threading
import time
from datetime import datetime

import config.settings as cfg
from utils import site_paths

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_RUNS_KEPT = 50            # số lần chạy giữ lại trong state
LOCK_STALE_DEFAULT = 1200     # 20 phút không heartbeat = chủ lock đã chết


# ─── PATHS (điểm duy nhất — hedge F10) ───────────────────────────────────────

def _data_dir() -> str:
    folder = getattr(cfg, "ALERTS_STATE_DIR", "data") or "data"
    if not os.path.isabs(folder):
        folder = os.path.join(ROOT, folder)
    return folder


def _state_path() -> str:
    # State per-site (QĐ B); LOCK đi đường riêng vì QĐ chốt: lock DÙNG CHUNG process-wide.
    return site_paths.per_site("scheduler_state.json", _data_dir())


def _lock_path() -> str:
    return os.path.join(_data_dir(), "scheduler.lock")


# STATE_FILE là slot override cho test/CLI; code đọc qua _active_state_path().
STATE_FILE = _state_path()
_DEFAULT_STATE_PATH = STATE_FILE
LOCK_FILE = _lock_path()


def _active_state_path() -> str:
    """Đường dẫn scheduler state lúc gọi. Test gán STATE_FILE → tôn trọng; không → resolve per-site."""
    if STATE_FILE != _DEFAULT_STATE_PATH:
        return STATE_FILE
    return _state_path()


def _lock_stale_after() -> int:
    value = getattr(cfg, "SCHEDULER_LOCK_STALE", None) or LOCK_STALE_DEFAULT
    return int(value)


# ─── STATE ───────────────────────────────────────────────────────────────────

def read_state() -> dict:
    """State gần nhất; file thiếu/hình hỏng → coi như chưa chạy lần nào."""
    path = _active_state_path()
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return {"jobs": data.get("jobs") or {}, "runs": data.get("runs") or []}
        except Exception:
            pass
    return {"jobs": {}, "runs": []}


def _save_state(state: dict) -> None:
    path = _active_state_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
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


def record_run(job: str, status: str, exit_code: int, error: str = "") -> None:
    """Ghi dấu vết một lần chạy — CHỈ gọi khi job thực sự chạy."""
    state = read_state()
    now = datetime.now().isoformat(timespec="seconds")
    state["jobs"][job] = {
        "last_run": now,
        "last_status": status,
        "exit_code": exit_code,
        "last_error": (error or "")[:300],
    }
    runs = state["runs"] + [{"job": job, "at": now, "status": status,
                             "exit_code": exit_code}]
    state["runs"] = runs[-MAX_RUNS_KEPT:]
    _save_state(state)


def status() -> dict:
    """{jobs, runs, running} — running = tên job đang giữ lock, hoặc None."""
    state = read_state()
    return {"jobs": state["jobs"], "runs": state["runs"], "running": lock_holder()}


def recent_runs(limit: int = 10) -> list:
    return read_state()["runs"][-limit:][::-1]


# ─── LOCK (chống hai job chồng nhau) ─────────────────────────────────────────

_STEAL_ATTEMPTS = 3   # số lần thử tạo/giật lock trước khi bỏ lượt (có process khác nhanh chân hơn)


def _read_lock() -> dict:
    """Nội dung lock; {} = KHÔNG có chủ hợp lệ (file thiếu, hoặc rác không parse được)."""
    if not os.path.exists(LOCK_FILE):
        return {}
    try:
        with open(LOCK_FILE, encoding="utf-8") as f:
            raw = f.read()
    except OSError:
        return {}
    if not raw.strip():
        # File vừa được os.open(O_CREAT|O_EXCL) tạo, payload chưa kịp ghi (cửa sổ
        # vài micro-giây). Coi là ĐANG GIỮ, heartbeat lấy theo mtime: process khác
        # không giật mất lock vừa tạo, mà lock cụt thật (chủ chết giữa chừng) vẫn
        # hết hạn được theo tuổi file.
        try:
            return {"pid": None, "job": "", "heartbeat": os.path.getmtime(LOCK_FILE)}
        except OSError:
            return {}
    try:
        data = json.loads(raw)
    except Exception:
        return {}            # rác (crash đúng lúc ghi) = không có chủ, được phép giật
    return data if isinstance(data, dict) else {}


def _lock_age(lock: dict) -> float:
    """Tuổi lock tính theo heartbeat; heartbeat rác → vô cùng (coi như đã chết)."""
    try:
        return time.time() - float(lock.get("heartbeat") or 0)
    except (TypeError, ValueError):
        return float("inf")


def lock_holder() -> str:
    """Job đang chạy (theo lock còn sống), hoặc '' / None khi không có."""
    lock = _read_lock()
    if not lock or _lock_age(lock) > _lock_stale_after():
        return None
    return lock.get("job") or None


def _create_lock_exclusive(job: str) -> bool:
    """Tạo lock bằng O_CREAT|O_EXCL — nhiều process cùng gọi thì CHỈ MỘT thắng.

    Cách cũ (đọc-thấy-trống-rồi-ghi) có khe hở: hai process cùng đọc ra "chưa ai
    giữ" rồi cùng ghi, kẻ sau đè lock kẻ trước → hai job chạy chồng nhau.
    """
    parent = os.path.dirname(LOCK_FILE)
    if parent:
        os.makedirs(parent, exist_ok=True)
    payload = json.dumps({"pid": os.getpid(), "job": job, "heartbeat": time.time()})
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY          # Windows: byte thô, không đổi \n thành \r\n
    try:
        fd = os.open(LOCK_FILE, flags, 0o644)
    except FileExistsError:
        return False
    try:
        os.write(fd, payload.encode("utf-8"))
        os.fsync(fd)                  # payload xuống đĩa trước khi process khác đọc
    except OSError:
        pass
    finally:
        os.close(fd)
    return True


def _steal_lock() -> None:
    """Dọn lock hết hạn/rác: rename sang tên riêng rồi xóa.

    Không xóa thẳng: giữa lúc đọc và lúc xóa, chủ cũ có thể đã nhả lock và ta sẽ
    xóa nhầm lock MỚI của người khác. os.replace nguyên tử nên chỉ một process
    giật được mỗi lần; kẻ thua nhận FileNotFoundError và bỏ qua.
    """
    victim = f"{LOCK_FILE}.stale.{os.getpid()}.{time.time_ns()}"
    try:
        os.replace(LOCK_FILE, victim)
    except OSError:
        return
    try:
        os.remove(victim)
    except OSError:
        pass


def acquire_lock(job: str) -> tuple:
    """(được chạy hay không, lý do tiếng Việt khi không được).

    Trần số lần thử: thua O_EXCL vì lock còn sống → trả lý do ngay; thua vì lock
    hết hạn/rác → giật rồi thử lại. Hết trần = có process khác cũng đang giành →
    bỏ lượt này (thà mất một lần chạy hơn để hai job chạy chồng nhau).
    """
    for _ in range(_STEAL_ATTEMPTS):
        if _create_lock_exclusive(job):
            return True, ""
        lock = _read_lock()
        if lock:
            age = _lock_age(lock)
            if age <= _lock_stale_after():
                return False, (f"job '{lock.get('job') or '?'}' đang chạy "
                               f"(PID {lock.get('pid') or '?'}, {int(age)}s trước)")
        _steal_lock()
    return False, "không giành được lock (process khác đang chạy cùng lúc) — bỏ lượt này"


def _write_lock(job: str) -> None:
    """Ghi lock nguyên tử — reader (watchdog/test) không bao giờ đọc thấy file cụt."""
    parent = os.path.dirname(LOCK_FILE)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = LOCK_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"pid": os.getpid(), "job": job, "heartbeat": time.time()}, f)
        os.replace(tmp, LOCK_FILE)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def touch_lock() -> None:
    """Gia hạn heartbeat — chỉ khi ta còn là chủ lock."""
    lock = _read_lock()
    if lock.get("pid") == os.getpid():
        _write_lock(lock.get("job") or "?")


def release_lock() -> None:
    """Xóa lock của CHÍNH process này; lock của người khác thì để nguyên."""
    lock = _read_lock()
    if lock.get("pid") == os.getpid():
        try:
            os.remove(LOCK_FILE)
        except OSError:
            pass


# ─── HEARTBEAT (job dài phải giữ lock còn sống) ──────────────────────────────

HEARTBEAT_INTERVAL = 30.0     # giây giữa 2 lần gia hạn lock khi job còn chạy


class _Heartbeat:
    """Thread nền renew lock cho tới khi job kết thúc — chết cùng process."""

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread = None

    def _loop(self) -> None:
        while not self._stop.wait(HEARTBEAT_INTERVAL):
            try:
                touch_lock()
            except Exception:
                pass

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)


# ─── JOB TABLE ───────────────────────────────────────────────────────────────

SCHEDULER_TRAFFIC_ENABLE = bool(getattr(cfg, "SCHEDULER_TRAFFIC_ENABLE", False))


def _guard_rank() -> tuple:
    from utils.rank_tracker import can_run_check
    return can_run_check()


def _guard_gsc() -> tuple:
    from utils.gsc_client import can_run_fetch
    return can_run_fetch()


def _guard_traffic() -> tuple:
    from utils.rate_limiter import can_run_session
    return can_run_session()


def _run_rank() -> int:
    """Check xếp hạng bản không hỏi CAPTCHA — 07:00 không có ai gõ phím."""
    import asyncio
    from utils.rank_tracker import run_rank_check_cli
    asyncio.run(run_rank_check_cli(interactive=False))
    return 0


def _run_gsc() -> int:
    """run_gsc_fetch_cli() tự sys.exit(1) khi thiếu credentials — run_job bắt lại."""
    from utils.gsc_client import run_gsc_fetch_cli
    run_gsc_fetch_cli()
    return 0


def _run_traffic() -> int:
    """1 session traffic qua utils/automation.py: module gốc vẫn dùng can_run_session()
    để chặn và mark_session_run() chỉ khi session xong — scheduler không tự đếm."""
    from utils.automation import run_one_session
    return run_one_session(use_search=True)

def _guard_backlink() -> tuple:
    """Rỗng = không có gì để verify — chạy tay cũng vô nghĩa, bảo owner thêm link trước."""
    from utils import backlinks as bl
    links = bl.load_links()
    if links:
        return True, ""
    return False, ("danh sách backlink trống — thêm link đã thật sự đặt: "
                   'python main.py --backlink-add "https://site-nguoi-khac/bai-co-link-cua-ban"')

def _run_backlink() -> int:
    """Verify link đã đặt còn sống — đúng engine --backlink-check, lịch sự với host lạ."""
    from utils.backlink_checker import run_backlink_check_cli
    return run_backlink_check_cli()


def _guard_report() -> tuple:
    """Report đọc lại dữ liệu có sẵn — luôn chạy được, không guard chặn."""
    return True, ""


def _run_report() -> int:
    """Ghẽ data/report.html mới nhất — đọc mọi nguồn dữ liệu hiện có, không request."""
    from utils.html_report import run_html_report_cli
    return run_html_report_cli()


def _guard_daily() -> tuple:
    """Báo cáo ngày không chặn gì — trống dữ liệu thì tin tự nói thiếu cái gì."""
    return True, ""


def _run_daily() -> int:
    """Báo cáo buổi sáng gộp rank/GSC/việc-hôm-nay — qua kênh alerts (console khi TẮT)."""
    from utils.daily_report import run_daily_cli
    return run_daily_cli()


def _guard_weekly() -> tuple:
    """Báo cáo tuần tự chống spam ở weekly_digest (1 lần/tuần ISO qua state) —
    job chạy hàng ngày cũng an toàn: tuần đã gửi chỉ in nhắc rồi thoát."""
    return True, ""


def _run_weekly() -> int:
    """Báo cáo tuần gộp rank/GSC/AEO — đánh dấu tuần CHỈ KHI send thành công."""
    from utils.weekly_digest import run_weekly_cli
    return run_weekly_cli(force=False)


# guard/runner lưu TÊN hàm, không lưu object: monkeypatch module là đổi được hành vi
JOBS = {
    "rank": {"desc": "Kiểm tra vị trí từ khóa trên Google",
             "hours": list(getattr(cfg, "SCHEDULER_RANK_HOURS", [7, 13, 19])),
             "guard": "_guard_rank", "runner": "_run_rank"},
    "gsc": {"desc": "Lấy dữ liệu Search Console (clicks/impressions)",
            "hours": list(getattr(cfg, "SCHEDULER_GSC_HOURS", [9])),
            "guard": "_guard_gsc", "runner": "_run_gsc"},
    "backlink": {"desc": "Verify backlink đã đặt còn sống",
                 "hours": list(getattr(cfg, "SCHEDULER_BACKLINK_HOURS", [])),
                 "guard": "_guard_backlink", "runner": "_run_backlink"},
    "report": {"desc": "Xuất report.html gộp SERP+GSC+audit+backlink (đọc dữ liệu có sẵn)",
               "hours": list(getattr(cfg, "SCHEDULER_REPORT_HOURS", [])
                             or getattr(cfg, "SCHEDULER_GSC_HOURS", [9])),
               "guard": "_guard_report", "runner": "_run_report"},
    "daily": {"desc": "Báo cáo buổi sáng gộp 1 tin (rank tail + GSC tail + việc hôm nay)",
              "hours": [7],
              "guard": "_guard_daily", "runner": "_run_daily"},
    "weekly": {"desc": "Báo cáo tuần gộp rank/GSC/AEO 1 tin — 1 lần/tuần (chạy ngày nào cũng chỉ gửi thứ 2 đầu tiên nó gặp)",
               "hours": [9],
               "guard": "_guard_weekly", "runner": "_run_weekly"},
    "traffic": {"desc": "1 session traffic — mặc định TẮT, quyết định của owner",
                "hours": [],
                "guard": "_guard_traffic", "runner": "_run_traffic"},
}

CLOCK_NOTE = "Giờ thật do Windows Task Scheduler quyết định — xem docs/SETUP_SCHEDULER.md"


def _hours_text(job: dict) -> str:
    return ", ".join(f"{int(h):02d}:00" for h in job["hours"]) or "không tự chạy"


def describe_jobs() -> list:
    """Mỗi dòng một job — cho `--run-job` sai tên và docs/SETUP_SCHEDULER.md."""
    lines = [f"  {name:<8} {job['desc']} | {_hours_text(job)}"
             for name, job in JOBS.items()]
    lines.append(f"  ({CLOCK_NOTE}; giờ ở trên là lịch mong muốn trong config/settings.py)")
    return lines


def run_job(name: str) -> int:
    """Chạy 1 job theo tên. Không bao giờ raise — Task Scheduler chỉ cần exit code."""
    print(f"[Scheduler] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} — job '{name}'")

    job = JOBS.get(name)
    if job is None:
        print(f"[Scheduler] Không có job '{name}'. Job hợp lệ:")
        for line in describe_jobs():
            print(line)
        return 2

    if name == "traffic" and not SCHEDULER_TRAFFIC_ENABLE:
        print("[Scheduler] Traffic đang TẮT theo quyết định của owner "
              "(SCHEDULER_TRAFFIC_ENABLE=False trong config/settings.py) — bỏ qua.")
        return 0

    allowed, reason = globals()[job["guard"]]()
    if not allowed:
        print(f"[Scheduler] {name}: module gốc từ chối — {reason}")
        return 0

    got_lock, why = acquire_lock(name)
    if not got_lock:
        print(f"[Scheduler] {name}: chưa chạy được — {why}")
        return 0

    code, status_txt, error = 1, "error", ""
    heartbeat = _Heartbeat()
    heartbeat.start()
    try:
        code = int(globals()[job["runner"]]() or 0)
        status_txt = "ok" if code == 0 else "error"
        error = "" if code == 0 else f"Job trả về exit code {code}"
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        status_txt = "ok" if code == 0 else "error"
        error = (f"Job kết thúc sớm bằng sys.exit({code}) — "
                 "thiếu cấu hình/credential, xem docs/SETUP_GSC.md")
    except BaseException as e:
        code, status_txt = 1, "error"
        error = f"{type(e).__name__}: {str(e)[:200]}"
    finally:
        heartbeat.stop()
        try:
            record_run(name, status_txt, code, error)
        except Exception as e:
            print(f"[Scheduler] Không ghi được state: {type(e).__name__}: {e}")
        release_lock()

    if code == 0:
        print(f"[Scheduler] {name}: xong.")
    else:
        print(f"[Scheduler] {name}: lỗi — {error}")
    notify_after_job(name, code, status_txt, error)
    return code


# ─── NOTIFY (tin Telegram tóm tắt sau job — mặc định TẮT, owner bật cùng ALERTS) ──

def notify_after_job(name: str, code: int, status_txt: str = "", error: str = "") -> bool:
    """Gửi 1 tin ngắn sau job. KHÔNG bao giờ raise, không đổi exit code của job.

    Mặc định TẮT (SCHEDULER_NOTIFY_ENABLE=False). Bật chỉ có tác dụng khi
    ALERTS_ENABLE=True — gửi hay không đều do settings quyết định.
    """
    del error  # error đã in ra --scheduler-status; tin Telegram chỉ tóm tắt đủ dùng
    if not bool(getattr(cfg, "SCHEDULER_NOTIFY_ENABLE", False)):
        return False
    try:
        from utils import alerts
        status_txt = status_txt or ("ok" if int(code or 0) == 0 else "error")
        lines = [f"⏱️ Scheduler — job '{name}': {status_txt} (exit {int(code or 0)})"]
        if name == "rank" and status_txt == "ok":
            lines.append(f"  Cảnh báo đang chờ: {len(alerts.pending_alerts())}")
        ok = alerts.send("\n".join(lines))
        if not ok:
            print("[Scheduler] Tin tóm tắt chưa gửi được — xem log Telegram trong alerts.")
        return ok
    except Exception as e:
        print(f"[Scheduler] Gửi tin tóm tắt lỗi (job vẫn tính là xong): {type(e).__name__}: {e}")
        return False


# ─── STATUS (CLI --scheduler-status + GUI đọc file, không đọc in-process) ─────

def format_status() -> list:
    st = status()
    lines = [f"[Scheduler] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} — {CLOCK_NOTE}"]
    lines.append("  Job:")
    for name, job in JOBS.items():
        hours = _hours_text(job)
        info = st["jobs"].get(name)
        if info is None:
            lines.append(f"    {name:<8} {hours:<20} chưa chạy lần nào")
            continue
        tail = " — đang chạy" if st["running"] == name else ""
        lines.append(f"    {name:<8} {hours:<20} lần cuối {info['last_run']} → "
                     f"{info['last_status']} (exit {info['exit_code']}){tail}")
        if info.get("last_error"):
            lines.append(f"             lỗi: {info['last_error']}")
    lines.append("  Gần đây:")
    runs = st["runs"][-5:][::-1]
    if not runs:
        lines.append("    (chưa có lần chạy nào)")
    for run in runs:
        lines.append(f"    {run['at']}  {run['job']:<8} {run['status']} (exit {run['exit_code']})")
    if st["running"]:
        lines.append(f"  đang chạy: {st['running']} — job khác sẽ bỏ qua cho tới khi xong")
    return lines


def run_status_cli() -> int:
    for line in format_status():
        print(line)
    return 0
