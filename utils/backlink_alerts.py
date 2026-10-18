# -*- coding: utf-8 -*-
"""utils/backlink_alerts.py — G-2: cảnh báo mất backlink qua Telegram/console.

So state check backlink LẦN TRƯỚC với lần VỪA XONG trong cùng lệnh
--backlink-check (0 request mới — thiết bị đo là lần check trước đã lưu trong
data/backlink_status.json):

- Trang đích chết (404/410/5xx) hoặc không đọc được mà trước đó sống;
- Link tới site biến mất (đã có has_link, giờ không);
- Link chuyển sang nofollow/sponsored/ugc (mất giá trị). Trang chết không
  cần cờ nofollow — mất hoàn toàn rồi.

Dùng chung state chống spam của alerts module (1 tin / ngày / link, key
'backlink:<key>') — link mất tiếp tục vắng mặt thì dứt một tin duy nhất.
Alert ERROR_ENABLE=False (mặc định tool) → chỉ in console, không gửi đi đâu.
Hook máy móc pattern engine xếp hạng: chạy SAU khi state đã ghi, không giữ
lỗi — backlink check không chết theo bộ cảnh báo.
"""
from utils import backlinks as bl

# Cột mốc entry còn "đáng kể": trạng thái sống + có link + dofollow.
def is_intact(entry: dict) -> bool:
    entry = entry if isinstance(entry, dict) else {}
    status = entry.get("status")
    try:
        status = int(status)
    except (TypeError, ValueError):
        status = 0
    return bool(entry.get("has_link")) and bool(entry.get("dofollow")) \
        and 200 <= status < 400 and not entry.get("error")


def alert_key(entry_key: str) -> str:
    """Key của state chống spam — phân biệt rank-sent 'backlink:<key>'."""
    return f"backlink:{entry_key}"


def build_alerts(prev_state: dict, new_state: dict, domain: str = "") -> list[dict]:
    """[alert] mỗi link đáng kể lần trước mà lần này mất giá trị.
    Link mới (chưa có trong prev) không tạo tin — 'lần đầu check' không phải 'mất'.
    Không raise, không cần cả hai state đủ — thiếu, entry là {} và thua."""
    alerts = []
    for key, prev in (prev_state or {}).items():
        prev = prev if isinstance(prev, dict) else {}
        if not is_intact(prev):
            continue       # lần trước đã có vấn đề — không thêm tin mới
        new = (new_state or {}).get(key)
        new = new if isinstance(new, dict) else None
        url = (prev.get("url") or new.get("url") or "").strip()
        if new is None:
            # URL biến mất khỏi danh sách (owner gỡ link) — là quyết định của
            # owner, không phải Google/xóa web → không cảnh báo.
            continue
        if not is_intact(new):
            alerts.append(_message(new, domain=domain) | {"keyword": alert_key(key)})
    return alerts


def _message(entry: dict, domain: str = "") -> dict:
    url = str(entry.get("url") or "")
    status = entry.get("status")
    try:
        status = int(status)
    except (TypeError, ValueError):
        status = 0
    if status == 0:
        msg = (f"🔴 Backlink không đọc được: {url}\n"
               "Trang để link không hồi âm — lần check sau sẽ thử lại (hoặc --backlink-refresh).")
    elif status >= 400:
        mean = "chết (404/410)" if status in (404, 410) else f"hỏng (HTTP {status})"
        msg = (f"🔴 Backlink {mean}: {url}\nTrang đích mất — còn sống khác có thể")
    elif not entry.get("has_link"):
        msg = (f"⚠️ Link tới {domain or 'site'} đã BIÊN MẤT khỏi trang: {url}\n"
               "Trang còn sống nhưng không còn chứa link. Kiểm tra tay lý do —")
    else:
        rels = " / ".join(entry.get("rel_seen") or []) or "rel chặn"
        msg = (f"⚠️ Link chuyển NOFOLLOW ({rels}): {url}\n"
               "Link còn đó nhưng không chuyển uy tín nữa.")
    return {"message": msg}


def evaluate(prev_state: dict, new_state: dict, domain: str = "") -> list[dict]:
    """API tương thích engine xếp hạng: [(alert)] dạng {keyword, message}."""
    return build_alerts(prev_state, new_state, domain=domain)


# ─── HOOK: gửi sau --backlink-check (dùng máy sending của alerts) ───────────

def check_and_notify(prev_state: dict, new_state: dict, domain: str = "") -> int:
    """Giao các alert vừa tạo. Dùng lại notify của alerts: state chống spam 1
    tin/ngày/link, Telegram/console, gửi hỏng dừng cho lượt sau thử lại.
    Không bao giờ raise — backlink check không chết theo bộ cảnh báo."""
    from utils import alerts
    try:
        return alerts.notify(evaluate(prev_state, new_state, domain=domain))
    except Exception as e:
        print(f"[Alert] ⚠️ Không chạy được cảnh báo backlink "
              f"({type(e).__name__}: {str(e)[:120]}) — kết quả check vẫn bình thường.")
        return 0
