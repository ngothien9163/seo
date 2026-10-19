# -*- coding: utf-8 -*-
"""utils/outreach.py — T32: sổ liên hệ đặt link (outreach tracker).

Câu hỏi thật của owner: "mail hỏi đặt link cho site nào rồi? người ta đồng ý
chưa? link đã sống chưa?" — việc liên hệ làm BẰNG TAY ngoài tool (mạng X, mail,
tin nhắn). Tool chỉ làm 2 việc, không làm gì hơn:

1. **GHI SỔ** — mỗi lời đề xuất 1 dòng trong `data/outreach.json` (per-site khi
   đã migrate), 4 trạng thái: **proposed** (đã gửi đề xuất) → **agreed** (người
   ta đồng ý) → **placed** (link đã sống vào backlinks.json — lúc đó hệ
   `--backlink-check` lo phần còn sống/chết) hoặc **dead** (mai một — chờ lâu
   không đặt / họ từ chối).
2. **NHẮC** trong báo cáo ngày: đề xuất ≥ `OUTREACH_REMIND_PROPOSED` (7) ngày
   chưa phản hồi → nhắc follow-up đúng 1 nhịp (không nhắc lại bộ này hàng ngày
   trừ khi đúng chu kỳ — nhắc thêm là spam chính mình); đồng ý ≥
   `OUTREACH_REMIND_AGREED` (5) ngày chưa đặt → nhắc gửi anchor/đào lại.

KHÔNG tự liên hệ, KHÔNG gửi mail, KHÔNG crawl site người ta, KHÔNG tự thêm vào
backlinks.json khi state placed (in khuyên dùng --backlink-add — quyết định của
owner; link sống qua được verify thì mới đáng). Reuse `_link_key` + `TIME_FMT`
của backlinks.json — cùng chuẩn id/đệm thời gian.
"""
import json
import os
from datetime import datetime

import config.settings as cfg
from utils import site_paths
from utils.backlinks import _link_key, TIME_FMT

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STATES = ("proposed", "agreed", "placed", "dead")
STATE_LABEL = {"proposed": "đã đề xuất, chờ phản hồi",
               "agreed": "đã đồng ý, chờ đặt link",
               "placed": "link đã sống",
               "dead": "mai một"}
# mỗi state đặt khi CHUYỂN ĐẾN nó → timestamp tự ghi đúng 1 lần
STAGE_FIELD = {"proposed": "proposed_at", "agreed": "agreed_at",
               "placed": "placed_at", "dead": "dead_at"}


def _default_state_path() -> str:
    return site_paths.per_site("outreach.json",
                               os.path.join(ROOT, getattr(cfg, "OUTREACH_STATE_DIR", "data")))


OUTREACH_FILE = _default_state_path()      # test gán OUTREACH_FILE → _state_path() tôn trọng


def _state_path() -> str:
    if OUTREACH_FILE != _default_state_path():
        return OUTREACH_FILE
    return _default_state_path()


def _now() -> str:
    return datetime.now().strftime(TIME_FMT)


def load_outreach() -> dict:
    """{"items": {linkkey: {...}}} — file thiếu/hỏng → sổ trống, không raise."""
    try:
        with open(_state_path(), encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("items") if isinstance(data, dict) else None
        if isinstance(items, dict):
            clean = {k: v for k, v in items.items()
                     if isinstance(v, dict) and state_of(v)}
            return {"items": clean}
    except Exception:
        pass
    return {"items": {}}


def save_outreach(data: dict) -> None:
    """Atomic (tmp + os.replace) — crash giữa chừng không cụt sổ."""
    path = _state_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def state_of(item: dict) -> str:
    st = str((item or {}).get("state") or "")
    return st if st in STATES else ""


def normalize_key(url: str) -> str:
    """Key của một lời đề xuất = chuẩn URL trang đích (cùng chuẩn backlinks.json).

    Trang đích nên là BÀI CỤ THỂ chứa chỗ đặt link (bài blog, trang resource)
    chứ không phải trang chủ — đề xuất trên trang chủ tổng quát khó được chấp nhận.
    """
    return _link_key(url)


def find_item(key_part: str) -> tuple:
    """Tìm mục theo key chuẩn / substring URL (không phân biệt thường hoa).
    Trả (linkkey, item) hoặc ("", None) khi 0/2+ khớp (để caller gõ rõ hơn)."""
    data = load_outreach()
    part = str(key_part or "").strip().lower()
    hits = [(k, it) for k, it in data["items"].items()
            if part == k or part in str(it.get("url", "")).lower()]
    if len(hits) == 1:
        return hits[0]
    return "", None


def add_item(url: str, kw: str = "", contact: str = "", note: str = "",
             title: str = "") -> tuple:
    """Thêm/mở lại lời đề xuất → (ok, msg). Trùng key + còn sống → báo không thêm."""
    key = normalize_key(url)
    if not key:
        return False, "URL trang đích không hợp lệ — ví dụ: https://spa-review.vn/top-spa-mi-hcm"
    data = load_outreach()
    old = data["items"].get(key)
    if old and state_of(old) == "placed":
        return False, "URL này đã đặt link rồi (state placed) — dùng --backlink-add để vào danh sách verify."
    prev_state = state_of(old) if old else ""
    reopened = old and prev_state == "dead"   # mở vòng mới: proposed_at RESET, mốc dọn
    item = dict(old) if old else {}           # BẢN COPY — tránh mutation aliasing
    item.update({
        "url": str(url or "").strip(), "kw": str(kw or "").strip(),
        "contact": str(contact or "").strip(), "note": str(note or "").strip(),
        "title": str(title or "").strip(), "state": "proposed",
        "proposed_at": _now() if reopened else ((old or {}).get("proposed_at") or _now()),
        "agreed_at": "", "placed_at": "", "dead_at": "",
        "updated": _now()})
    data["items"][key] = item
    save_outreach(data)
    if reopened:
        return True, f"Đã MỞ LẠI đề xuất {key} (trước đó mai một) — đếm lại từ hôm nay."
    if old:
        return True, f"Đã cập nhật {key} (vẫn {STATE_LABEL['proposed']})."
    return True, f"Đã ghi sổ đề xuất {key} ({STATE_LABEL['proposed']})."


def set_state(key_part: str, state: str, note: str = "") -> tuple:
    """Chuyển trạng thái 1 mục → (ok, msg). Được đi lui (agreed → proposed) rồi."""
    key, item = find_item(key_part)
    if not key:
        data = load_outreach()
        n = sum(1 for k, it in data["items"].items()
                if str(key_part or "").strip().lower() in k
                or str(key_part or "").strip().lower() in str(it.get("url", "")).lower())
        if n > 1:
            return False, f"'{key_part}' khớp {n} mục — gõ thêm ký tự cho khớp 1."
        if not data["items"]:
            return False, "Sổ outreach trống — thêm bằng --outreach-add URL."
        return False, f"Không tìm thấy '{key_part}' — xem: --outreach-list."
    st = str(state or "").strip().lower()
    if st not in STATES:
        return False, f"Trạng thái phải là 1 trong: {'|'.join(STATES)} (mà không phải '{state}')."
    old = state_of(item)
    item["state"] = st
    item[STAGE_FIELD[st]] = _now()
    item["updated"] = _now()
    if note:
        prev = str(item.get("note") or "")
        item["note"] = (prev + ("; " if prev else "") + note).strip("; ")
    data = load_outreach()
    data["items"][key] = item
    save_outreach(data)
    extra = ""
    if st == "placed" and old != "placed":
        extra = " — khuyên: python main.py --backlink-add '" + str(item.get("url", "")) + "' để hệ verify theo dõi."
    if st == "dead":
        extra = " — không nhắc nữa; mở lại bằng --outreach-add URL này."
    return True, f"{key}: đã ghép \"{STATE_LABEL[st]}\" ({old} → {st}).{extra}"


def remove_item(key_part: str) -> tuple:
    """Xóa vĩnh viễn 1 mục khỏi sổ (dead rồi mở lại không được — prefer set dead)."""
    key, item = find_item(key_part)
    if not key:
        return False, f"Không tìm thấy mục khớp '{key_part}' — xem: --outreach-list."
    data = load_outreach()
    gone = data["items"].pop(key)
    save_outreach(data)
    return True, f"Đã xóa {key} ({str(gone.get('url', ''))})."


# ─── NHẮC trong báo cáo ngày ────────────────────────────────────────────────

def reminder_lines(now=None) -> list:
    """Dòng nhắc cho daily report — quá hạn mới nhắc (≤2 dòng, không spam):
    proposed quá hạn → "đã N ngày chưa phản hồi"; agreed quá hạn → "chưa đặt link".
    placed do hệ backlink-check lo; dead không nhắc."""
    cfg_prop = int(getattr(cfg, "OUTREACH_REMIND_PROPOSED", 7))
    cfg_agr = int(getattr(cfg, "OUTREACH_REMIND_AGREED", 5))
    today = now or datetime.now()
    lines = []
    try:
        data = load_outreach()
    except Exception:
        return []
    items = data.get("items", {})
    for _k, it in sorted(items.items(), key=lambda kv: str(kv[1].get("proposed_at") or "")):
        st = state_of(it)
        since = str(it.get(STAGE_FIELD.get(st, "updated")) or "")
        if not since:
            continue
        try:
            days = (today - datetime.strptime(since, TIME_FMT)).days
        except ValueError:
            continue
        if st == "proposed" and days >= cfg_prop:
            lines.append(f"- '{str(it.get('title') or it.get('url') or '')[:60]}' "
                         f"({_short_host(it.get('url', ''))}) đã {days} ngày chờ phản hồi "
                         f"— nhắc 1 nhịp hoặc đánh dead.")
        elif st == "agreed" and days >= cfg_agr:
            lines.append(f"- '{str(it.get('title') or it.get('url') or '')[:60]}' "
                         f"({_short_host(it.get('url', ''))}) đồng ý {days} ngày chưa đặt link "
                         f"— gửi anchor / nhắc lại, quá hạn đánh dead.")
        if len(lines) >= 2:
            break
    return lines


def _short_host(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(str(url or "")).netloc or "?"
    except Exception:
        return "?"


# ─── BÁO CÁO SỔ (console + html section dùng chung) ────────────────────────

def list_rows() -> list:
    """[{key, url, host, title, kw, contact, note, state, status, stage, days}] —
    xếp chú ý trước: proposed → agreed → placed → dead, trong cùng nhóm thì
    bài chờ lâu hơn lên trước."""
    data = load_outreach()
    today = datetime.now()
    rows = []
    for key, it in data["items"].items():
        st = state_of(it)
        since = str(it.get(STAGE_FIELD.get(st, "updated")) or "")
        try:
            days = (today - datetime.strptime(since, TIME_FMT)).days if since else -1
        except ValueError:
            days = -1
        rows.append({"key": key, "url": str(it.get("url") or ""),
                     "host": _short_host(it.get("url", "")),
                     "title": str(it.get("title") or ""), "kw": str(it.get("kw") or ""),
                     "contact": str(it.get("contact") or ""), "note": str(it.get("note") or ""),
                     "state": st, "status": STATE_LABEL.get(st, st),
                     "stage": since, "days": days})
    rows.sort(key=lambda r: (STATES.index(r["state"]), -r["days"], r["key"]))
    return rows


def list_text() -> str:
    rows = list_rows()
    if not rows:
        return ("Sổ outreach trống — thêm: python main.py --outreach-add "
                "\"https://site-nguoi/bai-co-phuc-vu\" --outreach-kw \"anchor\"")
    lines = ["== SỔ OUTREACH (liên hệ đặt link) ==",
             f'{"Trang đích":<44}{"Trạng thái":<30}{"Ngày":<12}{"Từ khóa/anchor"}',
             "-" * 100]
    for r in rows:
        addr = str(r["title"] or r["url"] or r["key"])[:42]
        stage = "hôm nay" if r["days"] <= 0 else f'{r["days"]} ngày'
        lines.append(f"{addr:<44}{r['status']:<30}{stage:<12}{r['kw']}")
        if r["url"] != addr:
            lines.append(f"    {r['url']}")
        if r["note"]:
            lines.append(f"    ghi chú: {r['note']}")
    return "\n".join(lines)


# ─── CLI (main.py đọc cờ qua _flag_value rồi truyền vào) ────────────────────

def run_add_cli(url: str, kw: str = "", contact: str = "", note: str = "",
                title: str = "") -> int:
    if not (url or "").strip():
        print('Cách dùng: --outreach-add "URL-trang-đích" [--outreach-kw "anchor"] '
              '[--outreach-note "..."] [--outreach-contact "..."] [--outreach-title "..."]')
        print("Trang đích nên là 1 BÀI CỤ THỂ (không phải trang chủ) — chỗ bạn xin đặt link.")
        return 2
    ok_flag, msg = add_item(url, kw=kw, contact=contact, note=note, title=title)
    print(msg)
    return 0 if ok_flag else 2


def run_list_cli() -> int:
    print(list_text())
    return 0


def run_set_cli(key_part: str, state: str, note: str = "") -> int:
    if not key_part or not state:
        print("Cách dùng: --outreach-set \"URL-hoặc-một-phần\" --outreach-state "
              f"{'|'.join(STATES)} [--outreach-note \"nguyên nhân\"]")
        print("Gợi ý: set placed xong chạy --backlink-add để hệ verify phần còn sống/chết.")
        return 2
    ok_flag, msg = set_state(key_part, state, note)
    print(msg)
    return 0 if ok_flag else 2


def run_remove_cli(key_part: str) -> int:
    if not key_part:
        print('Cách dùng: --outreach-remove "URL-hoặc-một-phần" (xóa vĩnh viễn — '
              "chỉ thôi quan tâm thì --outreach-set ... --outreach-state dead)")
        return 2
    ok_flag, msg = remove_item(key_part)
    print(msg)
    return 0 if ok_flag else 2
