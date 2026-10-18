# -*- coding: utf-8 -*-
"""utils/gsc_alerts.py — G-B3: cảnh báo sớm imps rớt qua Telegram/console.

So impressions của từng query giữa 2 snapshot GSC gần nhất (0 request mới —
thiết bị đo là dữ liệu GSC vừa fetch/about đã lưu trong gsc_history.json):

- Query được Google phơi nhiều mốc trước (≥ GSC_ALERT_MIN_IMPS impressions)
  mà mốc mới rớt về < GSC_ALERT_DROP_RATIO (50%) — Google đang giảm phơi trang
  cho query này, thường chỉ sign trước khi hạng SERP thật sự rớt;
- Query rớt khỏi dữ liệu hoàn toàn (mốc trước có ≥ MIN_IMPS, mốc mới không xuất
  hiện) — imps = 0 là số thật (Google ngừng phơi), vẫn là tin.

Không cảnh báo: query mốc mới tăng imps (mộc tin tốt), query mới xuất hiện
(tăng trưởng, không phải mất), cả hai mốc đều dưới MIN_IMPS (noise).

Dùng chung state chống spam của alerts module (1 tin/ngày/query, key
'gscdrop:<fold query>') — query tiếp tục yếu thì dứt một tin duy nhất.
ALERTS_ENABLE=False (mặc định) → chỉ in console, không gửi đi đâu.
Hook gọi SAU khi snapshot đã ghi xong trong run_gsc_fetch_cli; tự nuốt lỗi —
fetch GSC không chết theo bộ cảnh báo.
"""
from utils.gsc_client import _load_history, _fold
from utils import gsc_trend

MIN_IMPS = 30        # mốc "được phơi đáng kể" trước khi tính là mất
DROP_RATIO = gsc_trend.TREND_DROP_IMPS   # 0.5 — imps mới < 50% imps trước


def alert_key(query: str) -> str:
    """Key của state chống spam — phân biệt rank alerts (bare keyword)."""
    return f"gscdrop:{_fold(query)}"


def _message(query: str, old: int, new: int, domain: str = "") -> str:
    tag = f' — {domain}' if domain else ""
    if new == 0:
        return (f"📉 Query \"{query}\" biến mất khỏi Google: impressions {old} → 0{tag}\n"
                "Google ngừng phơi trang cho query này — thường chạy trước khi hạng rớt.")
    pct = round(new / old * 100)
    return (f"📉 Query \"{query}\" mất phơi nhanh: impressions {old} → {new} "
            f"(-{100 - pct}%){tag}\n"
            "Giảm phơi đi trước giảm clicks — xem --gsc-trend, chỉnh title/thêm nội dung nếu là query tracked.")


def evaluate(history: dict) -> list[dict]:
    """gsc_history dict → [alert] dạng {keyword: key, message}.

    So 2 snapshot gần nhất (theo thứ tự ngày key). Hàm thuần: chỉ đọc dict
    được đưa vào, không ghi file, không gọi mạng. Lỗi dữ liệu của query nào
    → bỏ query đó, không làm chết phần còn lại.
    """
    snaps = (history or {}).get("snapshots") or {}
    stamps = sorted(str(s) for s in snaps.keys())
    if len(stamps) < 2:
        return []
    prev_snap = snaps.get(stamps[-2]) or {}
    cur_snap = snaps.get(stamps[-1]) or {}
    if not isinstance(prev_snap, dict) or not isinstance(cur_snap, dict):
        return []
    prev_rows = prev_snap.get("rows") or {}
    cur_rows = cur_snap.get("rows") or {}

    out = []
    for q, prev_row in prev_rows.items():
        if not isinstance(prev_row, dict):
            continue
        try:
            old = int(prev_row.get("impressions") or 0)
        except (TypeError, ValueError):
            continue
        if old < MIN_IMPS:
            continue    # trước đó đã yếu → noise, không phải "mất phơi"
        cur_row = cur_rows.get(q)
        new = 0
        if isinstance(cur_row, dict):
            try:
                new = int(cur_row.get("impressions") or 0)
            except (TypeError, ValueError):
                continue
        # cur_row None → imps 0 (query vắng = Google ngừng phơi, số thật)
        if new / old >= DROP_RATIO:
            continue    # giữ mức phơi, hoặc tốt hơn → không phải tin xấu
        out.append({"keyword": alert_key(q),
                    "message": _message(q, old, new)})
    return out


def check_and_notify(history: dict = None, domain: str = "") -> int:
    """Hook sau --gsc fetch: so 2 snapshot gần nhất, gửi các query chưa gửi hôm nay.

    Dùng lại notify của alerts: state chống spam 1 tin/ngày/query, Telegram/console,
    lỗi gửi dừng cho lần sau thử lại. Không bao giờ raise — fetch GSC không chết theo
    bộ cảnh báo; history None → tự đọc file (sau fetch thì đã có mốc mới).
    """
    from utils import alerts
    try:
        h = history if history is not None else _load_history()
        return alerts.notify(evaluate(h))
    except Exception as e:
        print(f"[Alert] ⚠️ Không chạy được cảnh báo GSC "
              f"({type(e).__name__}: {str(e)[:120]}) — dữ liệu GSC vẫn được lưu bình thường.")
        return 0


def run_gsc_alerts_cli() -> int:
    """Entry `--gsc-alerts`: đánh giá 2 snapshot GSC gần nhất + gửi tin chưa gửi."""
    from utils import alerts
    mode = alerts.delivery_mode()
    print("=" * 70)
    print("  CANH BAO GSC QUERY MAT PHOI (G-B3)")
    print(f"  Kênh giao hàng: {mode}")
    print("=" * 70)
    h = _load_history()
    found = evaluate(h)
    pending = [a for a in found if not alerts.already_sent_today(a["keyword"])]
    if not pending:
        print("[Alert] Không có tin mới (chưa đủ 2 snapshot, imps không rớt, "
              "hoặc đã gửi hôm nay — 1 tin/ngày/query).")
        print("[Alert] Xem xu hướng: python main.py --gsc-trend")
        return 0
    sent = alerts.notify(pending)
    print(f"[Alert] {len(pending)} query mất phơi | {sent} tin đã giao qua {mode} "
          f"| mỗi query tối đa 1 tin/ngày.")
    return 0


def pending_queries() -> list[str]:
    """Debug: ['query' fold] đã được gửi tin hôm nay — không dùng trong hook."""
    from utils import alerts
    today = __import__("datetime").date.today().isoformat()
    return list((alerts._load_state()["sent"].get(today) or []))
