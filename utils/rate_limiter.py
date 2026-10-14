"""
utils/rate_limiter.py — Gi?i h?n t?n su?t session ?? tránh b? Google phát hi?n.

Lu?t:
- T?i ?a 25 session/ngày (c?u hình trong settings.MAX_SESSIONS_PER_DAY)
- T?i thi?u 5 phút gi?a các session
- T? ?ó?ng l?i n?u v??t quá gi?i h?n

L?u tr?ng thái vào file JSON ?? không b? reset khi restart.
"""
import json
import os
import time
from datetime import datetime, date

import utils.site_paths as _site_paths

_SESSION_NAME = "session_state.json"
_DEFAULT_STATE_PATH = _site_paths.site_file(_SESSION_NAME)
# Slot override cho test/CLI (test gán STATE_FILE); code đọc qua _state_path().
STATE_FILE = _DEFAULT_STATE_PATH


def _state_path() -> str:
    """Đường dẫn session state lúc gọi. Test gán STATE_FILE → tôn trọng; không → resolve per-site."""
    if STATE_FILE != _DEFAULT_STATE_PATH:
        return STATE_FILE
    return _site_paths.site_file(_SESSION_NAME)


def _load_state() -> dict:
    """Đọc trạng thái từ file."""
    path = _state_path()
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except:
            pass
    return {"date": "", "count": 0, "last_session": 0}

def _save_state(state: dict):
    """Ghi trạng thái ra file."""
    with open(_state_path(), "w") as f:
        json.dump(state, f)

def can_run_session(max_per_day: int = 25, min_interval: int = 300) -> tuple[bool, str]:
    """Kiểm tra có được chạy session mới không.
    Args:
        max_per_day: Số session tối đa/ngày (mặc định 25)
        min_interval: Giây tối thiểu giữa 2 session (mặc định 300)
    Returns:
        (True, "") nếu được phép, (False, "lý do") nếu bị chặn
    """
    state = _load_state()
    today = date.today().isoformat()

    # Nếu chưa có dữ liệu hôm nay → OK
    if state["date"] != today:
        return True, ""

    # Check giới hạn ngày
    if state["count"] >= max_per_day:
        next_day = "ngày mai"
        return False, f"Đã đạt giới hạn {max_per_day} session/ngày. Chờ {next_day}."

    # Check cooldown giữa các session
    if state["last_session"] > 0:
        elapsed = time.time() - state["last_session"]
        if elapsed < min_interval:
            wait = int(min_interval - elapsed)
            return False, f"Cooldown: chờ {wait}s nữa ({min_interval}s giữa các session)."

    return True, ""

def mark_session_run():
    """Ghi nhận một session đã chạy."""
    today = date.today().isoformat()
    state = _load_state()

    if state["date"] != today:
        state = {"date": today, "count": 0, "last_session": 0}

    state["count"] += 1
    state["last_session"] = time.time()
    _save_state(state)

def get_today_summary() -> dict:
    """Trả về thống kê hôm nay."""
    state = _load_state()
    today = date.today().isoformat()

    if state["date"] != today:
        return {"date": today, "ran": 0, "remaining": 25, "next_window": 0}

    remaining = 25 - state["count"]
    next_window = max(0, int(state["last_session"] + 300 - time.time())) if state["last_session"] > 0 else 0

    return {
        "date": today,
        "ran": state["count"],
        "remaining": max(0, remaining),
        "next_window": next_window,
    }
