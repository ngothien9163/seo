# -*- coding: utf-8 -*-
"""
utils/actions.py — gom "việc nên làm trước" từ 5 nguồn ĐÃ CÓ dữ liệu
(0 request mới): audit CAO, backlink có vấn đề, bài lẻo/phơi không ai bấm
(T30), outreach quá hạn (T32), PageSpeed dưới ngưỡng (T33).

Một gom, ba nơi dùng: section "Việc nên làm trước" trong report.html (T36),
block trong --daily-report và --weekly (T37). Nguồn nào hỏng tự bỏ qua —
hỏng 1 nguồn không chết collection. KHÔNG in token/mật khẩu; KHÔNG tự chạy
lệnh nào — mỗi việc chỉ kèm lệnh gợi ý cho owner tự chạy.
"""
import config.settings as cfg

ORDER = {"CAO": 0, "nặng": 1, "chờ": 2}
ALL_SOURCES = ("audit", "backlink", "post", "outreach", "pagespeed")


def _url_path_tail(url: str) -> str:
    """Đuôi path của URL để gắn cuối dòng việc — '/spa-nail' ('/' → '')."""
    from urllib.parse import urlparse
    path = (urlparse(url or "").path or "").rstrip("/")
    if not path or path == "/":
        return ""
    return "/" + path.rsplit("/", 1)[-1] if "/" in path else path


def collect_items(sources: tuple = ALL_SOURCES, now=None) -> list:
    """[item] — mỗi item {src, sev, text, tail, fix}, thứ tự PY theo ORDER.
    Hạn nguồn: audit 3, backlink/post 2, outreach/pagespeed tự cap 2."""
    items = []
    if "audit" in sources:
        # Lỗi audit mức CAO — nghiêm trọng nhất trên trang
        try:
            from utils.site_auditor import load_last_audit
            findings = load_last_audit() or []
            for f in findings[:3]:
                if f.get("severity") != "CAO":
                    continue
                items.append({"src": "audit", "sev": "CAO",
                              "text": f'{f.get("rule")}: {f.get("detail")}',
                              "tail": _url_path_tail(str(f.get("url") or "")),
                              "fix": "--audit-actions"})
        except Exception:
            pass
    if "backlink" in sources:
        # Link đã đặt rủi ro mất — bỏ qua dòng "Còn sống"
        try:
            from utils import backlinks as bl
            from utils.backlink_checker import state_rows
            _header, state_data = state_rows(bl.load_state())
            for row in [r for r in state_data if not str(r[0]).startswith("Còn sống")][:2]:
                items.append({"src": "backlink", "sev": "CAO",
                              "text": f"Link đã đặt {str(row[0]).lower()}: {row[1]}",
                              "tail": "", "fix": "--backlink-check"})
        except Exception:
            pass
    if "post" in sources:
        # Bài lẻo / phơi không ai bấm (T30) — đang kéo là tốt, bỏ
        try:
            from utils.post_report import build_post_rows
            for r in (x for x in build_post_rows()[:6] if x["state"] in ("dead", "show")):
                items.append({"src": "post", "sev": "nặng",
                              "text": f'Bài "{r["keyword"]}" {r["status"].lower()}: '
                                      f'{r["advice"]}',
                              "tail": _url_path_tail(str(r.get("url") or "")),
                              "fix": "--post-report"})
        except Exception:
            pass
    if "outreach" in sources:
        # Outreach quá hạn (T32) — reminder_lines tự cap 2
        try:
            from utils.outreach import reminder_lines
            for ln in (s.strip().lstrip("-").lstrip() for s in reminder_lines(now=now)):
                items.append({"src": "outreach", "sev": "chờ", "text": ln,
                              "tail": "", "fix": "--outreach-list"})
        except Exception:
            pass
    if "pagespeed" in sources:
        # PageSpeed dưới ngưỡng (T33) — weak_posts tự cap 2
        try:
            from utils.pagespeed import weak_posts
            for ln in weak_posts():
                items.append({"src": "pagespeed", "sev": "chờ",
                              "text": str(ln).strip().lstrip("-").lstrip(),
                              "tail": "", "fix": "--pagespeed-posts"})
        except Exception:
            pass
    items.sort(key=lambda it: ORDER.get(it.get("sev"), 3))
    return items[:8]


def priority_lines(items: list = None, n: int = 4,
                   sources: tuple = ALL_SOURCES, now=None) -> list:
    """[dòng text] cho --daily-report / --weekly: '[CAO] rule: detail (/tail) — lệnh'.
    Truyền items=None → tự collect theo sources."""
    its = collect_items(sources=sources, now=now) if items is None else items
    lines = []
    for it in its[:n]:
        line = f'[{it.get("sev", "?")}] {it.get("text") or ""}'
        if it.get("tail"):
            line += f' ({it["tail"]})'
        if it.get("fix"):
            line += f" — {it['fix']}"
        lines.append(line)
    return lines
