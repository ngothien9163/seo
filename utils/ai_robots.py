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
from urllib.parse import urlsplit

import requests

import config.settings as cfg
from utils import site_paths

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def robots_state_path() -> str:
    """File state lần chạy gần nhất — report HTML (T25) đọc lại, 0 request."""
    return site_paths.per_site("ai_robots_last.json", os.path.join(ROOT, "data"))

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
    """`--ai-robots` — 1 request robots.txt, in bảng trạng thái từng bot AI."""
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
    lines = report(text, status)
    for line in lines:
        print(line)
    # Lưu kết quả lần chạy — so sánh giữa các lần không cần fetch lại.
    try:
        import json
        payload = {"url": target, "status": status,
                   "bots": check_bots(text)}
        os.makedirs(os.path.dirname(state_path), exist_ok=True)
        tmp = state_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, state_path)
    except OSError:
        pass
    return 0


def run_ai_robots_gui() -> str:
    """GUI build riêng kết quả cuối để đổ vào textbox — không print."""
    target = (getattr(cfg, "TARGET_URL", "") or "").strip()
    if not target:
        return "[AIRobots] Chưa đặt TARGET_URL trong config/settings.py."
    url, status, text = robots_txt_of(target)
    if not url:
        return f"[AIRobots] TARGET_URL không hợp lệ ({target})."
    lines = report(text, status)
    return "\n".join(lines)
