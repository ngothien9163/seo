# -*- coding: utf-8 -*-
"""
utils/weekly_digest.py — C3: báo cáo tuần tổng hợp → Telegram 1 lần/tuần.

Gộp 3 nguồn (mỗi nguồn OPTIONAL — trống/hỏng thì bỏ phần đó, không làm chết
digest): rank_tracker.build_report (SERP) + gsc_client.build_report
(clicks/impressions) + aeo.build_report (AI nhắc brand). Dạng Telegram: bắn
phần nội dung thật của mỗi report, bỏ các dòng "=" trang trí; bảng đầy đủ vẫn
xem bằng --rank-report / --gsc-report / --aeo-report như cũ.

Chống spam: state data/weekly_digest.json ghi tuần ISO đã gửi; đánh dấu CHỈ
KHI send thành công — hỏng mạng thì tuần này chưa đánh dấu, lần chạy kế thử
lại. Reuse alerts.send: ALERTS_ENABLE=False → chỉ in console, token env thắng
settings, không bao giờ raise trong luồng gọi.

Chạy:
    python main.py --weekly          # build + gửi (1 lần/tuần)
    python main.py --weekly --force  # gửi lại bất chấp state tuần này
"""

import json
import os
from datetime import date

import config.settings as cfg
from utils import site_paths

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TELEGRAM_MAX = 4096          # giới hạn text của sendMessage

# ─── STATE: tuần đã gửi ──────────────────────────────────────────────────────


def _state_path() -> str:
    return site_paths.per_site("weekly_digest.json",
                               os.path.join(ROOT, getattr(cfg, "ALERTS_STATE_DIR", "data")))


STATE_FILE = _state_path()
_DEFAULT_STATE_PATH = STATE_FILE


def _active_path() -> str:
    """Test gán STATE_FILE → tôn trọng; không → resolve per-site lúc gọi (F10)."""
    if STATE_FILE != _DEFAULT_STATE_PATH:
        return STATE_FILE
    return _state_path()


def iso_week(day=None) -> str:
    """Ngày → '2026-W43' (tuần ISO — key của state, chống gửi lặp)."""
    d = day or date.today()
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _load_state() -> dict:
    try:
        with open(_active_path(), encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("sent"), dict):
            return data
    except Exception:
        pass                    # file thiếu/hỏng — coi như chưa gửi tuần nào
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


def sent_this_week(week: str = "") -> bool:
    return (week or iso_week()) in _load_state().get("sent", {})


def mark_sent(week: str = "") -> None:
    """Đánh dấu tuần đã gửi. State chỉ giữ tuần của năm nay trở đi — đủ hiểu."""
    week = week or iso_week()
    state = _load_state()
    sent = state.get("sent") or {}
    sent[week] = date.today().isoformat()
    this_year = f"{date.today().isocalendar().year}-W01"
    state["sent"] = {k: sent[k] for k in sorted(sent) if k >= this_year}
    _save_state(state)


# ─── BUILD: gộp 3 report, mỗi nguồn optional ────────────────────────────────


def _section(title: str, report, tail: int = 12) -> list[str]:
    """Một phần digest: tiêu đề + tối đa `tail` dòng cuối có nội dung thật
    (bỏ dòng trang trí '='/'─' trống và dòng trống)."""
    if not report or not str(report).strip():
        return []
    content = [ln.rstrip() for ln in str(report).strip().splitlines()
               if ln.strip() and not set(ln.strip()) <= {"=", "─", "-"}]
    if not content:
        return []
    return [f"── {title} ──"] + content[-tail:]


def build_digest() -> str:
    """Báo cáo gộp đầy đủ (caller lo cắt 4096). Nguồn trống/hỏng → bỏ phần đó."""
    import importlib

    sources = (("XẾP HẠNG (SERP)", "utils.rank_tracker"),
               ("SEARCH CONSOLE", "utils.gsc_client"),
               ("AEO (AI nhắc brand)", "utils.aeo"))

    sections: list[list[str]] = []
    for title, module in sources:
        try:
            text = importlib.import_module(module).build_report()
            sections.append(_section(title, text))
        except Exception:
            continue            # nguồn này trống/hỏng — nguồn khác vẫn theo

    # T31 — 1 dòng trend AEO theo tuần (≥2 tuần có dữ liệu mới hiện, tránh nhiễu)
    try:
        from utils.aeo import load_history
        from utils.gui_charts import aeo_trend_series, trend_compare, trend_words
        cur, prev, n = trend_compare(aeo_trend_series(load_history()))
        if cur is not None and prev is not None:
            sections.append(_section(
                "AEO TREND",
                f"{cur}% câu trả lời AI được nhắc brand tuần này (tuần trước {prev}% — "
                f"{trend_words(cur, prev)}; {n} tuần có dữ liệu trong 8 tuần gần nhất). "
                "Chart đầy đủ: tab 📢 AI Nói Gì → nút AEO TREND."))
    except Exception:
        pass                    # trend là phần tốt thêm — thiếu thì bỏ, không chết digest

    # T44 — TREND AUDIT: tổng lỗi mốc đầu → mốc mới nhất (reuse T41, 0 request)
    try:
        from utils.audit_trend import trend_summary_for_html
        trend = trend_summary_for_html()
        if trend and len(trend.get("rules") or []) >= 1:
            tf, tl = int(trend.get("total_first", 0)), int(trend.get("total_last", 0))
            n = int(trend.get("n_checks", 0))
            mark = "↓ tốt" if tl < tf else ("↑ xấu" if tl > tf else "không đổi")
            sections.append(_section(
                "TREND AUDIT",
                f"Tổng lỗi {tf} → {tl} qua {n} lần audit ({mark}). "
                "Chi tiết từng loại: python main.py --audit-trend."))
    except Exception:
        pass                    # trend là phần tốt thêm — thiếu thì bỏ, không chết digest

    # T44 — ĐỐI THỦ ĐANG LEO: domain tăng số lần xuất hiện top-10 (reuse T43)
    try:
        from utils.competitors import _domain_from_target, trend_counters
        from utils.rank_tracker import _load_history
        own = _domain_from_target(getattr(cfg, "TARGET_URL", ""))
        first, last = trend_counters(_load_history(), own)
        rows = sorted(((d, last.get(d, 0) - first.get(d, 0),
                        first.get(d, 0), last.get(d, 0))
                       for d in set(first) | set(last)), key=lambda t: -t[1])
        movers = [f"{d} {f0}→{l0} ({dv:+d})" for d, dv, f0, l0 in rows if dv > 0][:3]
        if movers:
            sections.append(_section(
                "ĐỐI THỦ ĐANG LEO",
                "Đang tăng lần xuất hiện top-10 (mốc đầu → mới nhất): "
                + "; ".join(movers) + ". Chi tiết: --competitors."))
    except Exception:
        pass                    # như các phần tốt thêm khác — thiếu thì bỏ, không chết digest

    try:
        from utils.actions import priority_lines
        weekly_actions = priority_lines(n=3)
        if weekly_actions:
            sections.append(_section("VIỆC ƯU TIÊN", "\n".join(weekly_actions)))
    except Exception:
        pass                    # như các phần tốt thêm khác — thiếu thì bỏ, không chết digest

    lines = [f"BÁO CÁO TUẦN — {site_paths.site_domain() or '(chưa cấu hình)'}",
             f"Tuần {iso_week()} ({date.today().isoformat()})"]
    any_data = False
    for s in sections:
        any_data = any_data or bool(s)
        lines.append("")
        lines.extend(s)
    if not any_data:
        lines.append("")
        lines.append("Chưa có dữ liệu — chạy --rank / --gsc / --aeo-check trước.")
    return "\n".join(lines)


def _clip(text: str, limit: int = TELEGRAM_MAX) -> str:
    """Cắt đúng 4096 ký tự, gãy ở biên dòng, đuôi ghi rõ là bị cắt."""
    if len(text) <= limit:
        return text
    head = text[:limit - 40].rsplit("\n", 1)[0]
    return head + "\n… (bị cắt — xem đầy đủ: --rank-report / --gsc-report)"


def run_weekly_cli(force: bool = False) -> int:
    """Entry `--weekly`: build + gửi qua kênh alerts; đánh dấu tuần CHỈ KHI
    send thành công (hỏng mạng → tuần này chưa đánh dấu để chạy lại)."""
    from utils.alerts import send, delivery_mode, _log

    week = iso_week()
    if not force and sent_this_week(week):
        _log(f"Tuần {week} đã gửi báo cáo rồi (1 lần/tuần). "
             "Xem chi tiết: --rank-report / --gsc-report / --aeo-report.")
        return 0

    ok = send(_clip(build_digest()))
    if ok:
        mark_sent(week)
        _log(f"Đã giao báo cáo tuần {week} qua kênh {delivery_mode()}.")
        return 0
    _log("⚠️ Chưa gửi được — tuần này chưa đánh dấu, lần --weekly kế sẽ thử lại.")
    return 1
