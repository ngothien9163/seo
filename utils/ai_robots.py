# -*- coding: utf-8 -*-
"""utils/ai_robots.py — T22: `--ai-robots` — AI crawler nào bị robots.txt chặn?

AEO (F9/T17) phụ thuộc engine đọc được site mình. Quản trị viên khác chặn bot AI
trong robots.txt (GPTBot, ClaudeBot, ...) để chống mô hình học trên nội dung —
quyết định hợp lệ, nhưng nếu site mình CHẶN bot, AI không đọc trực tiếp được
→ câu trả lời AI chỉ dựa dữ liệu bên thứ ba (thư mục, review) → AEO kém.
Lệnh này đọc lại robots.txt của site một lần, đối chiếu từng bot AI đã biết,
và IN BẢNG QUYẾT ĐỊNH — thông tin để owner tự cân nhắc, KHÔNG tự sửa robots.txt
tool không có quyền sửa cấu hình site, và chặn bot là quyết định của owner.

Nguyên tắc:
- 1 request duy nhất tới <host>/robots.txt (không làm nặng server, khớp cách audit).
- Thuần dữ liệu tách khỏi CLI: check_bots() nhận robots_text, test được không cần mạng.
- Không judgment cứng: trạng thái "không nêu" (không khai báo group cho bot đó) là
  kết luận hợp lệ — bot rơi vào group `*`; bảng mô tả chứ không khuyến cáo cứng.
"""
import os
import json
import time as time_mod
from urllib.parse import urlsplit

import requests

import config.settings as cfg
from utils import site_paths

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def robots_state_path() -> str:
    """File state lần chạy gần nhất — report HTML (T25) đọc lại, 0 request."""
    return site_paths.per_site("ai_robots_last.json", os.path.join(ROOT, "data"))


def robots_history_path() -> str:
    """T28 — lịch sử mốc check robots.txt (tối đa AI_ROBOTS_HISTORY_KEEP mốc).
    Cùng thư mục với state; drift = khác biệt mốc gần nhất so mốc trước."""
    return site_paths.per_site("ai_robots_history.json", os.path.join(ROOT, "data"))

# Danh mục AI crawler — tên theo quy ước robots.txt GroupUser-Agent.
# docs song song: khi thêm bot mới, chỉ chạm bảng này (thuần data).
AI_BOTS = {
    "GPTBot": "OpenAI — huấn luyện mô hình (không đụng câu trả lời ngay)",
    "OAI-SearchBot": "OpenAI — crawler search trong ChatGPT (ảnh hưởng trực tiếp AEO)",
    "ChatGPT-User": "OpenAI — crawl khi user bấm đọc link trong ChatGPT",
    "ClaudeBot": "Anthropic — huấn luyện Claude",
    "Claude-Web": "Anthropic — tên cũ của ClaudeBot (một số robots.txt vẫn để tên này)",
    "anthropic-ai": "Anthropic — crawl nội dung cho sản phẩm AI của Anthropic",
    "PerplexityBot": "Perplexity — crawler trả lời tìm kiếm AI (ảnh hưởng AEO trực tiếp)",
    "Google-Extended": "Google — nguồn dữ liệu cho Gemini (không ảnh hưởng Search thường)",
    "CCBot": "Common Crawl — tập dữ liệu mở, nhiều model học từ đây",
    "Bytespider": "ByteDance — crawler Doubao (câu trả lời AI tại châu Á)",
    "FacebookBot": "Meta — crawler AI cho các sản phẩm social",
    "Amazonbot": "Amazon — crawler cho Alexa/AI sản phẩm",
}
AI_BOTS_ORDER = list(AI_BOTS.keys())

# T28 — history tối đa 30 mốc (tuần 1 lần ≈ 7 tháng nhìn lại), đủ so drift
AI_ROBOTS_HISTORY_KEEP = 30

BOT_STATUS_ORDER = {"blocked": 0, "explicit": 1, "default": 2, "missing": 3}
BOT_KEYS = {"bot", "status", "paths"}
BOT_LABEL = {"blocked": "CHẶN", "explicit": "KHAI BÁO 1 phần", "default": "không nêu",
             "missing": "robots trống"}


def robots_url_for(url: str) -> str:
    """http(s)://host/robots.txt với host lấy từ URL site; không throw nếu URL bẩn."""
    parts = urlsplit((url or "").strip())
    if not parts.scheme or not parts.netloc:
        return ""
    root = f"{parts.scheme}://{parts.netloc}"
    return root + "/robots.txt"


def _fetcher_default(url: str):
    """(status, text) — status 0 không kết nối được; không retry, không loop."""
    try:
        resp = requests.get(url, timeout=15,
                            headers={"User-Agent": str(getattr(cfg, "AUDIT_USER_AGENT",
                                       "Mozilla/5.0")) or "Mozilla/5.0"},
                            allow_redirects=True)
    except Exception:
        return (0, "")
    try:
        text = resp.content.decode(resp.encoding or "utf-8", errors="replace")
    except (LookupError, TypeError):
        try:
            text = resp.content.decode("utf-8", errors="replace")
        except Exception:
            text = ""
    return (int(resp.status_code or 0), text)


def _groups(robots_text: str) -> list:
    """Nhóm robots.txt — reuse lại _parse_robots của site_auditor (không viết lại)."""
    from utils.site_auditor import _parse_robots
    return _parse_robots(robots_text or "")


def _folders(rules: list) -> tuple[list, list]:
    """(disallow_paths, allow_paths) riêng để mô tả trạng thái; không so khớp prefix."""
    out_dis, out_all = [], []
    for path, allow in rules:
        if allow:
            out_all.append(path)
        else:
            out_dis.append(path)
    return out_dis, out_all


def check_bots(robots_text: str) -> list:
    """Mỗi bot trong AI_BOTS_ORDER → {bot, vendor, status, paths}.

    status:
      - "blocked": có group riêng và chặn toàn site (Disallow root "/", không Allow "/" thắng)
      - "explicit": có group riêng nhưng không chặn root (chặn vài thư mục)
      - "default": KHÔNG có group riêng → bot rơi nhóm `*` (chuẩn robots: cho phép
        nếu không Disallow toàn site)
      - "missing": robots.txt rỗng/không parse ra group nào
    Chỉ mô tả — không quyết định đúng sai, chặn bot là quyết định của owner.
    """
    parsed_groups = _groups(robots_text or "")
    out = []
    for bot in AI_BOTS_ORDER:
        group = next((g for g in parsed_groups
                      if bot.lower() in (a.lower() for a in g["agents"])), None)
        if group is None:
            wild = next((g for g in parsed_groups if "*" in g["agents"]), None)
            if wild is None:
                out.append({"bot": bot, "vendor": AI_BOTS[bot], "status": "missing",
                            "paths": []})
            else:
                dis, _allw = _folders(wild["rules"])
                root_block = any(d == "/" for d in dis)
                out.append({"bot": bot, "vendor": AI_BOTS[bot],
                            "status": "blocked" if root_block else "default",
                            "paths": dis[:3]})
            continue
        dis, allw = _folders(group["rules"])
        root_block = any(d == "/" for d in dis)
        if root_block and not any(a == "/" for a in allw):
            out.append({"bot": bot, "vendor": AI_BOTS[bot], "status": "blocked",
                        "paths": dis[:3]})
        else:
            out.append({"bot": bot, "vendor": AI_BOTS[bot], "status": "explicit",
                        "paths": sorted(set(dis))[:3]})
    return out


STATUS_VERBOSE = {
    "blocked": "⛔ CHẶN toàn site",
    "explicit": "⚠️ KHAI BÁO — chặn một số thư mục",
    "default": "🌫️  KHÔNG nêu — rơi vào group `*`",
    "missing": "✅ robots.txt trống hoặc không khai báo",
}


def report(robots_text: str, robots_status: int) -> list:
    """Dòng text cho CLI + GUI — không raise, không mạng."""
    if robots_status == 0:
        return ["[AIRobots] Không kết nối được robots.txt — kiểm tra site/mạng."]

    bots = check_bots(robots_text)
    if not any(b["status"] != "missing" for b in bots):
        return ["[AIRobots] robots.txt trống / không khai báo group nào.",
                "[AIRobots] Mặc định: cho phép — AI engine đọc trực tiếp được,"
                " tốt cho AEO."]

    # Statistics theo group
    blocked = [b for b in bots if b["status"] == "blocked"]
    explicit = [b for b in bots if b["status"] == "explicit"]
    default = [b for b in bots if b["status"] == "default"]
    lines = [
        f"[AIRobots] robots.txt đọc được (HTTP {robots_status}) — {len(blocked)} bot CHẶN,"
        f" {len(explicit)} bot KHAI BÁO 1 phần, {len(default)} bot nêu trong group `*`.",
        "",
        f"{'Bot':<18} {'Trạng thái':<32} Vendor — chặn trên gì",
        "─" * 96,
    ]
    for b in bots:
        extra = ""
        if b["status"] == "blocked" and b["paths"]:
            extra = "(Disallow: /)"
        elif b["paths"]:
            extra = "(Disallow: " + ", ".join(b["paths"]) + ")"
        lines.append(f"{b['bot']:<18} {STATUS_VERBOSE[b['status']]:<32} "
                     f"{b['vendor']}  {extra}")
    lines += ["",
              "Chặn bot AI là quyết định hợp lệ (chống rỉ nội dung) — cân nhắc nếu đang muốn AEO:",
              "• OAI-SearchBot / PerplexityBot nhiều ảnh hưởng trực tiếp nhất tới AI nhắc brand;",
              "• Google-Extended chỉ huấn luyện Gemini, không ảnh hưởng Search/hiển thị;",
              "• sửa robots.txt là TAY trên site của mình — tool này chỉ báo cáo."]
    return lines


# ─── T28: DRIFT — so tran trạng thái bot giữa các lần check robots.txt ──────

def _bot_fingerprint(bots: list) -> dict:
    """List bots (check_bots) → {bot: (status, paths tuple)} — so được bằng ==."""
    fp = {}
    for b in (bots or []):
        if not isinstance(b, dict) or not b.get("bot"):
            continue
        fp[str(b["bot"])] = (str(b.get("status") or ""),
                             tuple(str(p) for p in (b.get("paths") or [])))
    return fp


def diff_fingerprints(new_fp: dict, old_fp: dict) -> list:
    """Hai fingerprint → các dòng mô tả khác biệt (bot, old, new).
    Drift bot nào chưa từng thấy (bot mới bị khai) cũng bắt: old thiếu → 'trước: không nêu'."""
    lines = []
    for bot in sorted(set(new_fp) | set(old_fp)):
        new = new_fp.get(bot)
        old = old_fp.get(bot)
        if new == old:
            continue
        old_txt = (f"{BOT_LABEL.get(old[0], old[0])}" + (f" ({', '.join(old[1])})" if old[1] else "")
                   if old else "chưa từng được khai báo")
        new_txt = (f"{BOT_LABEL.get(new[0], new[0])}" + (f" ({', '.join(new[1])})" if new[1] else "")
                   if new else "không còn được nêu trong robots.txt")
        lines.append((bot, old_txt, new_txt))
    return lines


def format_drift(diff_rows: list, old_at: str, new_at: str) -> list:
    """drift rows diff_fingerprint → số dòng thông báo (hoặc [] khi không đổi)."""
    if not diff_rows:
        return []
    out = ["",
           "[AIRobots] ⚠️ ROBOTS.TXT THAY ĐỔI so lần check trước "
           f"({old_at} → {new_at}):"]
    for bot, old_txt, new_txt in diff_rows:
        out.append(f"  • {bot}: {old_txt} → {new_txt}")
    out.append("  (ai sửa robots.txt là quyết định trang quản trị — AI đọc trực tiếp "
               "site mình phụ thuộc theo, xem lại bảng trên để cân nhắc AEO)")
    return out


def load_history() -> list:
    """File history thiếu/hỏng → [] (không raise)."""
    try:
        with open(robots_history_path(), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    snaps = data.get("snapshots") if isinstance(data, dict) else None
    if not isinstance(snaps, list):
        return []
    return [s for s in snaps if isinstance(s, dict)]


def append_snapshot(payload: dict) -> list:
    """Ghi 1 mốc check (atomic, giữ AI_ROBOTS_HISTORY_KEEP mốc gần nhất). Trả history mới."""
    path = robots_history_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    snaps = load_history()
    snaps.append(payload)
    snaps = snaps[-AI_ROBOTS_HISTORY_KEEP:]
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"snapshots": snaps}, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    except OSError:
        pass
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
    return snaps


def drift_lines_for_text(history: list, new_bots: list) -> tuple:
    """drift dòng text (CLI/GUI): format_drift với chấm thời gian now thật."""
    new_fp = _bot_fingerprint(new_bots)
    for snap in reversed(history):
        if not isinstance(snap, dict) or not snap.get("bots"):
            continue
        old_fp = _bot_fingerprint(snap.get("bots"))
        if old_fp == new_fp:
            return [], snap
        rows = diff_fingerprints(new_fp, old_fp)
        at = str(snap.get("at") or "?")[:16].replace("T", " ")
        now = time_mod.strftime("%Y-%m-%d %H:%M")
        return format_drift(rows, at, now), snap
    return [], None


def drift_lines_for_html(history: list, new_bots: list) -> tuple:
    """drift rows cho HTML (T28): [(bot, old_txt, new_txt)], KHÔNG chấm 'now' —
    báo cáo được xuất sau, giờ xuất không thuộc nội dung so sánh. So cùng mốc
    logic như phần CLI (mốc trước khác biệt gần nhất)."""
    new_fp = _bot_fingerprint(new_bots)
    for snap in reversed(history):
        if not isinstance(snap, dict) or not snap.get("bots"):
            continue
        old_fp = _bot_fingerprint(snap.get("bots"))
        if old_fp == new_fp:
            return [], snap
        return diff_fingerprints(new_fp, old_fp), snap
    return [], None


def robots_txt_of(target: str, fetcher=None) -> tuple:
    """URL site hiện tại → (robots_url, status, text). fetcher test được cắm vào."""
    from utils.site_auditor import _default_fetcher
    url = robots_url_for(target)
    if not url:
        return ("", 0, "")
    f = fetcher or _fetcher_default
    status, text = f(url)
    return (url, int(status or 0), text or "")


def run_ai_robots_cli() -> int:
    """`--ai-robots` — 1 request robots.txt, in bảng trạng thái từng bot AI.
    T28: mỗi lần chạy ghi 1 mốc history + so mốc trước → in cảnh báo drift."""
    target = (getattr(cfg, "TARGET_URL", "") or "").strip()
    if not target:
        print("[AIRobots] ⚠️ Chưa đặt TARGET_URL trong config/settings.py.")
        return 2
    url, status, text = robots_txt_of(target)
    if not url:
        print(f"[AIRobots] ⚠️ TARGET_URL='{target}' không phân tích được scheme/host.")
        return 2
    state_path = robots_state_path()
    print(f"[AIRobots] Đọc {url}")
    bots = check_bots(text)
    history = load_history()
    drift_lines, _ = (drift_lines_for_text(history, bots)
                     if status != 0 else ([], None))
    lines = report(text, status) + drift_lines
    for line in lines:
        print(line)
    # Lưu kết quả lần chạy — so sánh giữa các lần không cần fetch lại.
    try:
        at = time_mod.strftime("%Y-%m-%dT%H:%M:%S")
        payload = {"url": target, "status": status, "bots": check_bots(text)}
        os.makedirs(os.path.dirname(state_path), exist_ok=True)
        tmp = state_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, state_path)
    except OSError:
        pass
    # T28 — mốc history (status 0 cũng ghi: mạng chết 1 lần không phá chuỗi so sánh)
    try:
        append_snapshot({"at": at, "status": status, "bots": bots})
    except Exception as e:
        print(f"[AIRobots] Không ghi được history: {type(e).__name__}: {e}")
    return 0


def run_ai_robots_gui() -> str:
    """GUI build riêng kết quả cuối để đổ vào textbox — không print.
    T28: gồm cả dòng drift so lần trước (đọc history) nhưng KHÔNG ghi mốc —
    người dùng bấm nút cho xem kết quả là xem; mốc ghi qua schedule/CLI."""
    target = (getattr(cfg, "TARGET_URL", "") or "").strip()
    if not target:
        return "[AIRobots] Chưa đặt TARGET_URL trong config/settings.py."
    url, status, text = robots_txt_of(target)
    if not url:
        return f"[AIRobots] TARGET_URL không hợp lệ ({target})."
    bots = check_bots(text)
    history = load_history()
    drift_lines, _ = drift_lines_for_text(history, bots)
    lines = report(text, status) + drift_lines
    return "\n".join(lines)
