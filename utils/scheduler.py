"""
utils/scheduler.py — F4: để lịch tự động chạy mà không cần mở GUI.

Đồng hồ thật là Windows Task Scheduler (quyết định đã duyệt ở spec F4): nó gọi

    python main.py --run-job rank      # 07:00 / 13:00 / 19:00
    python main.py --run-job gsc       # 09:00

Module này KHÔNG tự đếm giới hạn ngày và KHÔNG tự thức khuya: nó chỉ
1. chặn hai job chồng nhau (file lock theo PID + heartbeat),
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
    return os.path.join(_data_dir(), "scheduler_state.json")


def _lock_path() -> str:
    return os.path.join(_data_dir(), "scheduler.lock")


STATE_FILE = _state_path()
LOCK_FILE = _lock_path()


def _lock_stale_after() -> int:
    value = getattr(cfg, "SCHEDULER_LOCK_STALE", None) or LOCK_STALE_DEFAULT
    return int(value)


# ─── STATE ───────────────────────────────────────────────────────────────────

def read_state() -> dict:
    """State gần nhất; file thiếu/hình hỏng → coi như chưa chạy lần nào."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return {"jobs": data.get("jobs") or {}, "runs": data.get("runs") or []}
        except Exception:
            pass
    return {"jobs": {}, "runs": []}


def _save_state(state: dict) -> None:
    parent = os.path.dirname(STATE_FILE)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=1)
        os.replace(tmp, STATE_FILE)
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

def _read_lock() -> dict:
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception:
            return {}            # lock hỏng = không có chủ, giành được
        return {}
    return {}


def lock_holder() -> str:
    """Job đang chạy (theo lock còn sống), hoặc '' / None khi không có."""
    lock = _read_lock()
    if not lock:
        return None
    if time.time() - float(lock.get("heartbeat") or 0) > _lock_stale_after():
        return None
    return lock.get("job") or None


def acquire_lock(job: str) -> tuple:
    """(được chạy hay không, lý do tiếng Việt khi không được)."""
    lock = _read_lock()
    if lock:
        age = time.time() - float(lock.get("heartbeat") or 0)
        if age <= _lock_stale_after():
            return False, (f"job '{lock.get('job', '?')}' đang chạy "
                           f"(PID {lock.get('pid', '?')}, {int(age)}s trước)")
    parent = os.path.dirname(LOCK_FILE)
    if parent:
        os.makedirs(parent, exist_ok=True)
    _write_lock(job)
    return True, ""


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


# guard/runner lưu TÊN hàm, không lưu object: monkeypatch module là đổi được hành vi
JOBS = {
    "rank": {"desc": "Kiểm tra vị trí từ khóa trên Google",
             "hours": list(getattr(cfg, "SCHEDULER_RANK_HOURS", [7, 13, 19])),
             "guard": "_guard_rank", "runner": "_run_rank"},
    "gsc": {"desc": "Lấy dữ liệu Search Console (clicks/impressions)",
            "hours": list(getattr(cfg, "SCHEDULER_GSC_HOURS", [9])),
            "guard": "_guard_gsc", "runner": "_run_gsc"},
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
    return code


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
