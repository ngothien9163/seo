"""
utils/alerts.py — F3: não cảnh báo tụt hạng (dùng chung cho rank check, GSC, scheduler F4).

Ba tầng tách rời:
1. Rules engine THUẦN  — evaluate(checks): 2 lần check gần nhất → list cảnh báo, không đọc file.
2. Chống spam          — data/alerts_state.json: tối đa 1 tin/ngày/từ khóa.
3. Sender (Task 2)     — Telegram, có fallback console; mọi lỗi chỉ in log.

Chạy:
    python main.py --alerts        # xem cảnh báo hiện tại + kênh giao hàng
    GUI: tab "📈 Xếp Hạng"

Cấu hình: config/settings.py PHẦN F + docs/SETUP_ALERTS.md
"""
import json
import os
from datetime import date, timedelta

import config.settings as cfg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_KEEP_DAYS = 14        # state chống spam giữ bao nhiêu ngày trước khi prune
TOP10 = 10                  # ngưỡng "Top 10" trong thông điệp

# Sentinel: từ khóa không có dữ liệu hạng ở mốc đó (khác với pos = None = không vào top)
_MISSING = object()


# ─── PATH STATE (điểm duy nhất sinh ra path — hedge cho F10 multi-site) ──────

def _state_path() -> str:
    folder = getattr(cfg, "ALERTS_STATE_DIR", "data") or "data"
    if not os.path.isabs(folder):
        folder = os.path.join(ROOT, folder)
    return os.path.join(folder, "alerts_state.json")


STATE_FILE = _state_path()


# ─── 1. RULES ENGINE THUẦN ───────────────────────────────────────────────────

def _read_pos(entry) -> object:
    """entry trong history → int hạng, None (không vào top), hoặc _MISSING (thiếu dữ liệu)."""
    if not isinstance(entry, dict) or "pos" not in entry:
        return _MISSING
    v = entry["pos"]
    if v is None:
        return None
    if isinstance(v, bool):
        return _MISSING
    if isinstance(v, (int, float)):
        return int(v)
    return _MISSING


def _alert(keyword: str, kind: str, old, new, delta, message: str) -> dict:
    return {"keyword": keyword, "kind": kind, "old_pos": old,
            "new_pos": new, "delta": delta, "message": message}


def _suffix(domain: str) -> str:
    return f" — {domain}" if domain else ""


def _drop_message(keyword, old, new, delta, domain):
    depth = getattr(cfg, "RANK_CHECK_DEPTH", 100)
    if new is None:
        where = f"rơi khỏi top {depth} kết quả (đang hạng {old})"
    else:
        where = f"tụt {delta} hạng: từ hạng {old} xuống hạng {new}"
    return f'📉 "{keyword}" {where}{_suffix(domain)}'


def _top10_message(keyword, old, new, delta, domain):
    depth = getattr(cfg, "RANK_CHECK_DEPTH", 100)
    if new is None:
        fell = f"không còn trong top {depth} kết quả"
    else:
        fell = f"rớt xuống hạng {new} (tụt {delta} hạng)"
    return (f'🚨 "{keyword}" rớt khỏi Top {TOP10}: đang hạng {old} thì {fell}'
            f'{_suffix(domain)}')


def evaluate(checks: dict, domain: str = "") -> list[dict]:
    """
    So 2 lần check gần nhất trong rank history và sinh cảnh báo.
    checks: {iso_time: {keyword: {"pos": int|None, "url": str|None}}} — đúng schema
            rank_history.json. Hàm thuần: chỉ đọc dict được đưa vào.
    """
    if not isinstance(checks, dict):
        return []
    stamps = sorted(checks.keys())
    if len(stamps) < 2:
        return []          # chưa có mốc so sánh

    prev = checks.get(stamps[-2]) or {}
    current = checks.get(stamps[-1]) or {}
    if not isinstance(prev, dict) or not isinstance(current, dict):
        return []

    threshold = int(getattr(cfg, "RANK_ALERT_DROP", 5))
    watch_top10 = bool(getattr(cfg, "RANK_ALERT_TOP10_FALL", True))
    alerts: list[dict] = []

    for keyword, entry in current.items():
        old = _read_pos(prev.get(keyword))
        new = _read_pos(entry)
        if old is _MISSING or new is _MISSING:
            continue       # thiếu dữ liệu một trong hai mốc → không đủ căn cứ

        if old is None:
            continue       # trước đây chưa xếp hạng → không tính được "tụt"

        delta = None if new is None else new - old
        left_top10 = watch_top10 and old <= TOP10 and (new is None or new > TOP10)

        if left_top10:
            # một tin cho một chuyện: rớt Top 10 bao gồm cả chuyện rơi nhiều hạng
            alerts.append(_alert(keyword, "top10_fall", old, new, delta,
                                 _top10_message(keyword, old, new, delta, domain)))
        elif new is None:
            # tụt từ hạng đo được ra ngoài top N: không có con số, nhưng vẫn là tin
            alerts.append(_alert(keyword, "drop", old, None, None,
                                 _drop_message(keyword, old, None, None, domain)))
        elif delta >= threshold:
            alerts.append(_alert(keyword, "drop", old, new, delta,
                                 _drop_message(keyword, old, new, delta, domain)))

    return alerts


def evaluate_from_history() -> list[dict]:
    """Đọc rank history (import lười để module này không kéo theo Playwright)."""
    from utils.rank_tracker import _load_history
    history = _load_history() or {}
    return evaluate(history.get("checks") or {}, domain=history.get("domain") or "")


# ─── 2. STATE CHỐNG SPAM: 1 tin / ngày / từ khóa ─────────────────────────────

def _load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("sent"), dict):
                return data
        except Exception:
            pass           # state hỏng → coi như chưa gửi gì, không được làm chết check
    return {"sent": {}}


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


def _prune(sent: dict, today: str) -> dict:
    cutoff = (date.fromisoformat(today) - timedelta(days=STATE_KEEP_DAYS)).isoformat()
    kept = {}
    for day, keywords in sent.items():
        try:
            if day < cutoff:
                continue
        except TypeError:
            continue       # key không phải ngày → bỏ luôn
        if isinstance(keywords, list):
            kept[day] = keywords
    return kept


def already_sent_today(keyword: str, day: str = None) -> bool:
    day = day or date.today().isoformat()
    return keyword in (_load_state()["sent"].get(day) or [])


def mark_sent(keyword: str, day: str = None) -> None:
    today = day or date.today().isoformat()
    state = _load_state()
    sent = state.get("sent") or {}
    seen = sent.get(today)
    if not isinstance(seen, list):
        seen = []
    if keyword not in seen:
        seen.append(keyword)
    sent[today] = seen
    state["sent"] = _prune(sent, date.today().isoformat())
    _save_state(state)


def pending_alerts() -> list[dict]:
    """Cảnh báo của lần check gần nhất, đã lọc bỏ từ khóa gửi xong hôm nay."""
    return [a for a in evaluate_from_history() if not already_sent_today(a["keyword"])]
