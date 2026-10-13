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
    return int(getattr(cfg, "SCHEDULER_LOCK_STALE", LOCK_STALE_DEFAULT))


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
    with open(LOCK_FILE, "w", encoding="utf-8") as f:
        json.dump({"pid": os.getpid(), "job": job, "heartbeat": time.time()}, f)


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
