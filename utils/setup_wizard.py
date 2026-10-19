# -*- coding: utf-8 -*-
"""utils/setup_wizard.py — T14: wizard "Cài đặt lần đầu" cho owner mới.

GUI tab 🧙 chiếu trạng thái từng BƯỚC bật nhà: site & từ khóa → rank check
lần đầu → Search Console → Ollama → Telegram (tùy chọn) → WordPress (tùy
chọn). Không cấu hình gì thay owner — chỉ ĐỌC file/config hiện có và nói
bước nào xong, bước nào thiếu, thiếu thì lệnh/docs nào điền.

Nguyên tắc:
- KHÔNG mạng — mọi check là file/config thuần (ping Ollama là việc của
  tab 🤖 AI Engine + nút 🩺 DOCTOR; wizard không nhân bản cái đó).
- KHÔNG in token/mật khẩu — secret chỉ báo "đã điền" hay "để trống".
- Không bao giờ raise: file thiếu/hỏng coi như bước chưa xong.
- Giá trị InjectionPoint: hàm nhận `checks` (map tên check → (status,
  detail)) từ caller để test thuần, mặc định None → tự tính.
- Tùy chọn (Telegram/WP) KHÔNG chặn tổng thể — thiếu chỉ là "warn".
"""
import os

from utils import site_paths
from utils.keywords import load_keywords

# trạng thái text của từng nhóm bước — GUI vẽ lại theo list này
STEP_LABELS = {
    "site": "1. Site & từ khóa",
    "rank": "2. Check rank lần đầu",
    "gsc": "3. Search Console",
    "ollama": "4. Ollama (sinh bài)",
    "alerts": "5. Telegram cảnh báo (tùy chọn)",
    "wp": "6. WordPress đẩy nháp (tùy chọn)",
}

# 🔴 quy ước quan trọng: nhóm nào OPTIONAL (không chặn tổng thể mới sẵn sàng)
OPTIONAL = ("alerts", "wp")


def _gsc_credentials_path() -> str:
    import config.settings as cfg
    from utils.gsc_client import _resolve_path
    return _resolve_path(getattr(cfg, "GSC_CREDENTIALS_FILE", "") or "")


def _load_json(path: str):
    try:
        with open(path, encoding="utf-8") as f:
            import json
            return json.load(f)
    except Exception:
        return None


def _masked_announce(secret: str) -> str:
    """'đã điền (…xyz)' — KHÔNG in secret; spy leak-safe."""
    s = (secret or "").strip()
    if not s:
        return "để trống"
    return f"đã điền (…{s[-4:]})" if len(s) > 8 else "đã điền"


def wizard_steps() -> list[dict]:
    """[(key, done, optional, detail, hint)] theo thứ tự STEP_LABELS.

    done đủ dùng (bước chính), optional=True không tính vào "cons sẵn sàng".
    detail là dòng tóm tắt hiện trạng; hint là lệnh/docs khi chưa xong.
    """
    out = []
    for key, done, optional, detail, hint in (
        _step_site(), _step_rank(), _step_gsc(),
        _step_ollama(), _step_alerts(), _step_wp()):
        out.append({"key": key, "done": done, "optional": optional,
                    "detail": detail, "hint": hint})
    return out


def next_unclear_step(steps: list = None) -> str:
    """Key bước bắt buộc CHƯA xong (theo thứ tự) hoặc '' — GUI highlight nó."""
    for st in (steps if steps is not None else wizard_steps()):
        if st["optional"]:
            continue
        if not st["done"]:
            return st["key"]
    return ""


def ready_summary(steps: list = None) -> str:
    """(Dòng tổng cho GUI): 'X/Y bước bắt buộc đã xong — nên làm: <bước đầu>.'"""
    steps = steps if steps is not None else wizard_steps()
    req = [s for s in steps if not s["optional"]]
    done = sum(1 for s in req if s["done"])
    nxt = next_unclear_step(steps)
    if done == len(req):
        opts_miss = [STEP_LABELS[s["key"]] for s in steps
                     if s["optional"] and not s["done"]]
        return (f"{done}/{len(req)} bước bắt buộc OK — ⚠️ còn tùy chọn: "
                " ".join(o.split(". ", 1)[-1] for o in opts_miss) if opts_miss
                else f"{done}/{len(req)} bước bắt buộc OK — xong hết! 🎉")

    label = STEP_LABELS.get(nxt, "")
    return f"{done}/{len(req)} bước bắt buộc — nên làm trước: {label}"


def _step_site() -> tuple:
    dom = site_paths.site_domain()
    kws = load_keywords() or []
    if not dom:
        return ("site", False, False, "TARGET_URL chưa cấu hình (tab ⚙️ vẫn trống)",
                "Nhập domain ở tab ⚙️ Cài Đặt Chung rồi bấm 🔀 Áp dụng site")
    if not kws:
        return ("site", False, False, f"Site OK ({dom}) nhưng chưa có từ khóa nào",
                "Điền từ theo dõi ở tab ⚙️ (1 từ/dòng) rồi BẮT ĐẦU một lần để ghi keywords.json")
    return ("site", True, False,
            f"Site {dom} + {len(kws)} từ khóa ({', '.join(kws[:2])}…)", "")


def _step_rank() -> tuple:
    from utils.rank_tracker import _history_path
    data = _load_json(_history_path()) or {}
    checks = data.get("checks") if isinstance(data, dict) else None
    if not isinstance(checks, dict) or not checks:
        return ("rank", False, False, "Chưa check xếp hạng lần nào",
                "Tab 📈 → 🔄 KIỂM TRA XẾP HẠNG NGAY (cần Playwright; CAPTCHA hỏi tay)")
    return ("rank", True, False, f"Lần check gần nhất: {sorted(checks.keys())[-1][:10]}", "")


def _step_gsc() -> tuple:
    cred = _gsc_credentials_path()
    cred = (cred if cred and os.path.isfile(cred)
            else os.path.join(site_paths.ROOT, "config", "gsc_service_account.json"))
    if not os.path.isfile(cred):
        return ("gsc", False, False, "Chưa có file service account của GSC",
                "docs/SETUP_GSC.md — 5 bước tạo service account + cấp quyền trên property")
    path = site_paths.per_site("gsc_history.json", site_paths.DATA_ROOT)
    snaps = ((_load_json(path) or {}).get("snapshots") or {})
    if not snaps:
        return ("gsc", False, False, "Credential đã có nhưng CHƯA fetch lần nào",
                "Tab 📈 → 📊 LẤY DỮ LIỆU SEARCH CONSOLE (lỗi 403 = email SA chưa được cấp quyền trên property)")
    return ("gsc", True, False,
            f"GSC OK — snapshot mới nhất {sorted(snaps.keys())[-1][:10]}", "")


def _step_ollama() -> tuple:
    import config.settings as cfg
    url = str(getattr(cfg, "OLLAMA_URL", "") or "").strip()
    model = str(getattr(cfg, "CONTENT_MODEL", "") or "").strip()
    if not url or not model:
        return ("ollama", False, False, "OLLAMA_URL hoặc CONTENT_MODEL để trống (PHẦN C)",
                "Phần C config/settings.py — mặc định localhost:11434 + qwen3:30b-a3b")
    drafts = os.listdir(os.path.join(site_paths.ROOT, "content", "drafts")) \
        if os.path.isdir(os.path.join(site_paths.ROOT, "content", "drafts")) else []
    n = len([f for f in drafts if f.endswith(".md")])
    url_ok = bool(url) and bool(model)
    return ("ollama", url_ok and n > 0, False,
            (f"Ollama cấu hình ({url}, {model}) — {n} bản nháp đã sinh"
             if url_ok and n else
             (f"Ollama cấu hình ({url}) nhưng CHƯA sinh bài nào — tab 🤖 → ✍️ SINH BÀI"
              if url_ok else "OLLAMA_URL hoặc CONTENT_MODEL để trống (PHẦN C)")),
            "" if (url_ok and n) else
            'Cần server Ollama chạy + pull model; kiểm sâu: python main.py --generate "kw" --dry-run')


def _step_alerts() -> tuple:
    import config.settings as cfg
    import os as _os
    enabled = bool(getattr(cfg, "ALERTS_ENABLE", False))
    token = (_os.getenv("TELEGRAM_BOT_TOKEN")
             or str(getattr(cfg, "TELEGRAM_BOT_TOKEN", "") or "")).strip()
    chat = (_os.getenv("TELEGRAM_CHAT_ID")
            or str(getattr(cfg, "TELEGRAM_CHAT_ID", "") or "")).strip()
    if enabled and token and chat:
        return ("alerts", True, True,
                f"Telegram BẬT (token {_masked_announce(token)}, chat …{chat[-4:]})", "")
    if enabled:
        return ("alerts", False, True,
                f"ALERTS_ENABLE=True nhưng thiếu token/chat (token {_masked_announce(token)})",
                "docs/SETUP_ALERTS.md — token từ @BotFather + chat id")
    return ("alerts", False, True,
            "Tùy chọn — đang TẮT: cảnh báo chỉ in console (không nhắn tin)",
            "Muốn nhắn tin Telegram: docs/SETUP_ALERTS.md (~5 phút) rồi điền token + chat ở đây")


def _step_wp() -> tuple:
    import config.settings as cfg
    url = str(getattr(cfg, "WP_URL", "") or "").strip()
    user = str(getattr(cfg, "WP_USER", "") or "").strip()
    pw = (os.getenv("WP_APP_PASSWORD") or str(cfg.WP_APP_PASSWORD or "")).strip()
    if url and user and pw:
        return ("wp", True, True,
                f"WP OK ({url}, user {user}, pass {_masked_announce(pw)})", "")
    if url or user or pw:
        return ("wp", False, True,
                "WP điền được 1/3 đến 2/3 — đẩy bài nháp sẽ báo thiếu khi chạy",
                "PHẦN L config/settings.py + App Password ở env WP_APP_PASSWORD (ưu tiên settings)" if pw else
                "PHẦN L config/settings.py — App Password tạo trong WP admin → Profile → Application Passwords")
    return ("wp", False, True,
            "Tùy chọn — chưa cấu hình: --wp-push sẽ hướng dẫn khi chạy",
            "PHẦN L config/settings.py (WP_URL + user + App Password) khi cần đẩy bài nháp lên WordPress")


def run_wizard_cli() -> int:
    """Entry `--setup-wizard`: in bảng wizard đầy đủ, gợi ý docs để làm từng bước."""
    steps = wizard_steps()
    ok = "✓"
    miss = "✗"
    warn = "!"
    print("=" * 86)
    print("  CÀI ĐẶT LẦN ĐẦU — wizard các bước bật nhà (chỉ đọc config, 0 request)")
    print("=" * 86)
    for s in steps:
        mark = ok if s["done"] else (warn if s["optional"] else miss)
        line = f"  [{mark}] {STEP_LABELS[s['key']]:<38}"
        print(line + s["detail"])
        if not s["done"] and s["hint"]:
            print(f"       ↳ {s['hint']}")
    print("-" * 86)
    print(f"  {ready_summary(steps)}")
    print("  Chi tiết từng bước: docs/CHECKLIST_FIRST_RUN.md (CHECKLIST 'Bật nhà mới')")
    print("=" * 86)
    return 0
