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

import requests

import config.settings as cfg
from utils import site_paths

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_KEEP_DAYS = 14        # state chống spam giữ bao nhiêu ngày trước khi prune
TOP10 = 10                  # ngưỡng "Top 10" trong thông điệp
SEND_TIMEOUT = 15           # giây — sender không bao giờ được treo flow gọi nó

# Sentinel: từ khóa không có dữ liệu hạng ở mốc đó (khác với pos = None = không vào top)
_MISSING = object()


# ─── PATH STATE (điểm duy nhất sinh ra path — hedge cho F10 multi-site) ──────

def _state_path() -> str:
    folder = getattr(cfg, "ALERTS_STATE_DIR", "data") or "data"
    if not os.path.isabs(folder):
        folder = os.path.join(ROOT, folder)
    return site_paths.per_site("alerts_state.json", folder)


# Slot override cho test/CLI (test gán STATE_FILE); code đọc qua _active_path().
STATE_FILE = _state_path()
_DEFAULT_STATE_PATH = STATE_FILE


def _active_path() -> str:
    """Đường dẫn alerts state lúc gọi. Test gán STATE_FILE → tôn trọng; không → resolve per-site."""
    if STATE_FILE != _DEFAULT_STATE_PATH:
        return STATE_FILE
    return _state_path()


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


def _trend_message(keyword, old_avg, new_avg, delta, n, domain):
    return (f'🌡️ "{keyword}" xu hướng giảm dần: hạng TB từ {old_avg:.1f} '
            f'lên {new_avg:.1f} (xấu đi {delta:.1f} vị trí) trong {n} lần check gần '
            f'nhất — dự báo sẽ rớt nếu không can thiệp{_suffix(domain)}')


def _trend_slope(checks: dict, stamps: list[str], keyword: str) -> tuple:
    """
    Dốc xu hướng của 1 từ khóa trên chuỗi mốc (stamps đã sort).
    So trung bình hạng của 4 mốc mới nhất (nhóm "mới") với 4 mốc ngay trước đó
    (nhóm "cũ"). Trả (old_avg, new_avg, delta, n_mốc_dùng) hoặc None khi thiếu
    dữ liệu: mỗi nhóm phải đủ 4 mốc CÓ hạng đo được (None/không có entry thì
    nhóm không đủ — không ước lượng bằng nửa vời).
    """
    half = 4
    # đi ngược từ mốc mới nhất, chỉ thu hạng đo được của từ khóa này
    series: list[int] = []
    for st in reversed(stamps):
        p = _read_pos((checks.get(st) or {}).get(keyword))
        if p is _MISSING or p is None:
            break               # đứt chuỗi đo được — chỉ dùng đoạn gần nhất liên tục
        series.append(p)
        if len(series) >= half * 2:
            break
    if len(series) < half * 2:
        return None
    new_pts = series[:half]     # gần nhất nằm trước (đi ngược)
    old_pts = series[half:half * 2]
    old_avg = sum(old_pts) / half
    new_avg = sum(new_pts) / half
    return old_avg, new_avg, new_avg - old_avg, half * 2


def _trend_alerts(checks: dict, stamps: list[str], domain: str) -> list[dict]:
    """C4: quét từ khóa trong mốc mới nhất, cảnh báo khi dốc trung bình xấu đi >= ngưỡng."""
    if not bool(getattr(cfg, "RANK_ALERT_TREND_ENABLE", True)):
        return []
    drop = int(getattr(cfg, "RANK_ALERT_TREND_DROP", 3))
    window = max(int(getattr(cfg, "RANK_ALERT_TREND_WINDOW", 14)), 8)
    usable = stamps[-window:]
    if len(usable) < 8:
        return []               # cửa sổ chưa đủ 2 nhóm 4 mốc
    out: list[dict] = []
    for keyword in sorted((checks.get(usable[-1]) or {}).keys()):
        result = _trend_slope(checks, usable, keyword)
        if result is None:
            continue
        old_avg, new_avg, delta, n = result
        if delta >= drop:
            out.append(_alert(keyword, "trend_drop", round(old_avg, 1),
                              round(new_avg, 1), round(delta, 1),
                              _trend_message(keyword, old_avg, new_avg, delta,
                                             n, domain)))
    return out


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

    return alerts + _trend_alerts(checks, stamps, domain)


def evaluate_from_history() -> list[dict]:
    """Đọc rank history (import lười để module này không kéo theo Playwright)."""
    from utils.rank_tracker import _load_history
    history = _load_history() or {}
    return evaluate(history.get("checks") or {}, domain=history.get("domain") or "")


# ─── 2. STATE CHỐNG SPAM: 1 tin / ngày / từ khóa ─────────────────────────────

def _load_state() -> dict:
    path = _active_path()
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("sent"), dict):
                return data
        except Exception:
            pass           # state hỏng → coi như chưa gửi gì, không được làm chết check
    return {"sent": {}}


def _save_state(state: dict) -> None:
    path = _active_path()
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


# ─── 3. SENDER: Telegram, fallback console ───────────────────────────────────

def _telegram_fields() -> tuple[str, str]:
    """Env var thắng settings.py — token không buộc phải nằm trong file được git theo dõi."""
    token = (os.getenv("TELEGRAM_BOT_TOKEN")
             or str(getattr(cfg, "TELEGRAM_BOT_TOKEN", "") or "")).strip()
    chat = (os.getenv("TELEGRAM_CHAT_ID")
            or str(getattr(cfg, "TELEGRAM_CHAT_ID", "") or "")).strip()
    return token, chat


def is_configured() -> tuple[bool, str]:
    """(token + chat id đã đủ chưa, thông điệp hướng dẫn tiếng Việt)."""
    token, chat = _telegram_fields()
    if token and chat:
        return True, "Telegram đã sẵn sàng."
    return False, ("Chưa cấu hình Telegram — thêm TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID "
                   "vào config/settings.py (hướng dẫn: docs/SETUP_ALERTS.md).")


def delivery_mode() -> str:
    """Kênh thực sự dùng lúc này: 'telegram' hoặc 'console'."""
    if not bool(getattr(cfg, "ALERTS_ENABLE", False)):
        return "console"
    ok, _ = is_configured()
    return "telegram" if ok else "console"


def _scrub(text: str, *secrets: str) -> str:
    """Token/exception của requests có chứa URL mang bot token → bóc trước khi in."""
    out = str(text)
    for s in secrets:
        if s:
            out = out.replace(s, "***")
    return out


def _log(message: str) -> None:
    print(f"[Alert] {message}")


def send(message: str) -> bool:
    """
    Giao một tin. Trả True = đã thông báo xong (kể cả qua console), False = thất bại
    và caller nên thử lại ở lần check sau. Không bao giờ raise.
    """
    message = (message or "").strip()
    if not message:
        return False

    if not bool(getattr(cfg, "ALERTS_ENABLE", False)):
        _log(message)
        _log("ALERTS_ENABLE=False → mới chỉ in ra console, chưa gửi đi đâu.")
        return True

    ok, hint = is_configured()
    if not ok:
        _log(message)
        _log(hint)
        return True

    token, chat = _telegram_fields()
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": message},
            timeout=SEND_TIMEOUT,
        )
    except Exception as e:            # RequestException + mọi lỗi network khác
        _log(f"⚠️ Không gọi được Telegram ({type(e).__name__}: "
             f"{_scrub(str(e)[:160], token, chat)}) — tin chưa gửi.")
        return False

    try:
        data = resp.json()
    except Exception as e:
        _log(f"⚠️ Telegram trả phản hồi không đọc được ({type(e).__name__}) — tin chưa gửi.")
        return False

    if isinstance(data, dict) and data.get("ok"):
        _log(f"Đã gửi 1 cảnh báo qua Telegram (chat {chat[-4:]}).")
        return True

    reason = ""
    if isinstance(data, dict):
        reason = str(data.get("description") or "")
    _log(f"⚠️ Telegram từ chối ({reason or 'lỗi không rõ'}) — tin chưa gửi.")
    return False


def notify(alerts: list[dict]) -> int:
    """
    Gửi từng cảnh báo (bỏ qua từ khóa đã gửi hôm nay). Trả số tin đã giao.
    Mạng/Telegram hỏng ngay tin đầu tiên → dừng: không có nghĩa 18 từ khóa
    cùng lỗi mạng và mỗi lần retry mất tới 15 giây.
    """
    sent = 0
    for alert in alerts or []:
        keyword = (alert or {}).get("keyword")
        message = (alert or {}).get("message")
        if not keyword or not message or already_sent_today(keyword):
            continue
        if send(message):
            mark_sent(keyword)
            sent += 1
        else:
            _log("Dừng lượt cảnh báo này — chưa gửi sẽ được thử lại ở lần check sau.")
            break
    return sent


def check_and_notify() -> int:
    """Hook sau rank check: evaluate lịch sử + giao cảnh báo đang chờ. Không bao giờ raise."""
    try:
        return notify(pending_alerts())
    except Exception as e:
        _log(f"⚠️ Không chạy được bộ cảnh báo ({type(e).__name__}: {str(e)[:120]})"
             f" — xếp hạng vẫn được lưu bình thường.")
        return 0


def hint_pending() -> int:
    """Hook sau GSC fetch: chỉ nhắc số cảnh báo đang chờ, KHÔNG gửi (rank check mới là nơi gửi)."""
    try:
        pending = pending_alerts()
    except Exception as e:
        _log(f"⚠️ Không kiểm tra được cảnh báo chờ ({type(e).__name__}: {str(e)[:120]})")
        return 0
    if pending:
        _log(f"{len(pending)} cảnh báo xếp hạng đang chờ — gửi ngay: python main.py --alerts")
    return len(pending)


def run_alert_check_cli() -> int:
    """Entry `--alerts`: in cảnh báo đang chờ + kênh giao hàng. Không gửi trùng."""
    mode = delivery_mode()
    print("=" * 70)
    print("  CANH BAO TUT HANG (F3)")
    print(f"  Kênh giao hàng: {mode}")
    print("=" * 70)
    if mode == "console":
        enabled = bool(getattr(cfg, "ALERTS_ENABLE", False))
        if not enabled:
            _log("ALERTS_ENABLE=False → bật trong config/settings.py PHẦN F mới gửi Telegram.")
        else:
            _log(is_configured()[1])
    pending = pending_alerts()
    if not pending:
        _log("Không có cảnh báo mới (lịch sử chưa đủ 2 lần check, hoặc hạng không rơi).")
        _log("Xem lịch sử: python main.py --rank-report")
        return 0
    sent = notify(pending)
    _log(f"{len(pending)} cảnh báo | {sent} tin đã giao qua kênh {mode} "
         f"| mỗi từ khóa tối đa 1 tin/ngày.")
    return 0
