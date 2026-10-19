# -*- coding: utf-8 -*-
"""utils/post_report.py — T30: hiệu quả TỪNG BÀI VIẾT (--post-report + section posts).

Câu hỏi owner hỏi sau vài tuần viết bài: "bài nào đang kéo traffic, bài nào
điêu?" — không phải tổng site (--gsc-report) cũng không phải trang VIP
(--page-impact) mà mỗi BÀI tool đã push WP một dòng:

Ghép 5 nguồn có sẵn — 0 request mới:
- wp_pushed.json (plan_progress.load_pushed) — bài nào đã push WP + permalink
- draft chờ duyệt (plan_progress.scan_drafts) — chưa có URL (chưa xuất bản)
- GSC pages snapshot cuối (gsc_pages._snapshot_pages) — clicks/impressions từng URL
- aeo.ai_matrix() — engine nào nhắc brand theo từ khóa của bài
- indexnow state "known" — URL đã submit chưa (chỉ membership, không có ngày từng URL)

Ghép key: permalink khớp ĐÚNG (bỏ query + '/' cuối) trước, rồi slug từ khóa
(fold + gạch ngang) trong path GSC. AEO khớp fold CHÍNH XÁC từ khóa — ai_matrix
dùng từ khóa plan, trùng nguồn với WP push. Bài đã push mà còn draft cũ cùng từ
khóa thì draft bị bỏ (không đếm đôi).

Verdict từng bài: đang kéo (clicks>0) / hiển thị chưa ai bấm (imps>0, clicks 0)
/ lẻo (có trong GSC nhưng 0 imps) / chưa có dữ liệu GSC / draft chờ duyệt.
Tool chỉ ĐỌC và khuyên — mọi quyết định nội dung thuộc về owner.
"""
import json
from urllib.parse import urlsplit

from utils.gsc_client import _fold

_STATE_LABEL = {"pull": "đang kéo",
                "show": "hiển thị chưa bấm",
                "dead": "lẻo (0 imps)",
                "nodata": "chưa có dữ liệu GSC",
                "draft": "draft chờ duyệt"}
_STATE_ORDER = ("pull", "show", "dead", "nodata", "draft")


def _norm_key(url: str) -> str:
    """Khóa khớp GSC page ↔ WP link: host + path, bỏ query + '/' cuối, chữ thường."""
    try:
        p = urlsplit(str(url or ""))
        return f"{p.netloc}{p.path}".rstrip("/").lower()
    except Exception:
        return str(url or "").lower().rstrip("/")


def _page_agg(pages: dict) -> dict:
    """{_norm_key(url): {clicks, imps}} — '/x' và '/x/' là GỘP một trang
    (GSC trả trailing slash tùy query), khác query cùng trang cộng dồn."""
    out = {}
    for q, entries in (pages or {}).items():
        if not str(q or "").strip():
            continue
        for e in (entries or []):
            if not isinstance(e, dict) or not str(e.get("page") or "").strip():
                continue
            key = _norm_key(str(e["page"]).strip())
            if not key:
                continue
            rec = out.setdefault(key, {"clicks": 0, "imps": 0})
            rec["clicks"] += int(e.get("clicks") or 0)
            rec["imps"] += int(e.get("imps") or 0)
    return out


def _known_urls() -> set:
    """URL IndexNow đã submit (state 'known') — file thiếu/hỏng → rỗng."""
    try:
        from utils.indexnow import key_state_file
        with open(key_state_file(), encoding="utf-8") as f:
            state = json.load(f)
        urls = state.get("known") if isinstance(state, dict) else None
        return {str(u) for u in (urls or []) if u}
    except Exception:
        return set()


def _aeo_hit_for(kw: str, matrix: dict) -> tuple[int, int]:
    """(được nhắc, đã hỏi) qua AEO — khớp fold CHÍNH XÁC; chưa hỏi → (0, 0)."""
    fk = _fold(kw)
    for mkw, per in (matrix or {}).items():
        if _fold(str(mkw)) == fk:
            per = per or {}
            return (sum(1 for e in per.values() if (e or {}).get("mentioned")),
                    len(per))
    return (0, 0)


def build_post_rows(pushed=None, drafts=None, pages=None, known=None, matrix=None) -> list:
    """Mỗi bài 1 dòng: {keyword, url, clicks, imps, gsc, aeo_hit, aeo_asked,
    submit, state, status, advice} — xếp đang kéo trước, draft chờ duyệt sau.

    Arg None → tự nạp nguồn tương ứng; nguồn hỏng → rỗng, phần còn lại sống."""
    if pushed is None:
        try:
            from utils.plan_progress import load_pushed
            pushed = load_pushed()
        except Exception:
            pushed = {}
    if drafts is None:
        try:
            from utils.plan_progress import scan_drafts
            drafts = scan_drafts()
        except Exception:
            drafts = {}
    if pages is None:
        try:
            from utils.gsc_pages import _snapshot_pages
            pages = _snapshot_pages()[0]
        except Exception:
            pages = {}
    if known is None:
        known = _known_urls()
    if matrix is None:
        try:
            from utils.aeo import ai_matrix
            matrix = ai_matrix()
        except Exception:
            matrix = {}

    agg = _page_agg(pages)
    known_keys = {_norm_key(u) for u in (known or set())}

    rows = []
    pushed_keys = set()
    for fk, p in (pushed or {}).items():
        if not isinstance(p, dict):
            p = {}
        kw = str(p.get("keyword") or fk)
        link = str(p.get("link") or "")
        pushed_keys.add(_fold(kw))

        matched = agg.get(_norm_key(link)) if link else None
        if matched is None and link:
            slug = _fold(kw).replace(" ", "-")   # WP slug = từ khóa gạch ngang
            if len(slug) >= 4:                   # slug quá ngắn dễ khớp nhầm — bỏ
                for key in agg:
                    if f"/{slug}/" in f"{key}/":  # biên path — 'noi-mi' không dính 'noi-mi-quan-2'
                        matched = agg[key]
                        break
        clicks = (matched or {}).get("clicks", 0)
        imps = (matched or {}).get("imps", 0)

        if not link:
            state = "nodata"                   # đã push mà thiếu link — lỗi dữ liệu, không phải draft
        elif matched is None:
            state = "nodata"
        elif clicks > 0:
            state = "pull"
        elif imps > 0:
            state = "show"
        else:
            state = "dead"

        aeo_hit, aeo_asked = _aeo_hit_for(kw, matrix)
        submit = bool(link) and _norm_key(link) in known_keys

        frags = []
        if not link:
            frags.append("bài trong wp_pushed.json thiếu link — push lại để ghi permalink")
        elif state == "show":
            frags.append("phơi mà chưa ai bấm — review title/meta description")
        elif state == "dead":
            frags.append("lẻo — review nội dung + gắn link nội bộ từ bài đang kéo")
        elif state == "nodata":
            frags.append("GSC chưa thấy URL này (mới xuất bản cần vài ngày; chạy --gsc)")
        if aeo_asked and aeo_hit == 0:
            frags.append("AEO: hỏi rồi AI chưa nhắc — dán lại câu trả lời mới")
        elif link and not submit:
            frags.append("chưa submit IndexNow — python main.py --indexnow")
        advice = "; ".join(frags[:2])   # tối đa 2 — dòng dài là rối

        rows.append({"keyword": kw, "url": link, "clicks": clicks, "imps": imps,
                     "gsc": matched is not None, "aeo_hit": aeo_hit,
                     "aeo_asked": aeo_asked, "submit": submit,
                     "state": state, "status": _STATE_LABEL[state], "advice": advice})

    for dk, d in (drafts or {}).items():
        d = d if isinstance(d, dict) else {}
        kw = str(d.get("keyword") or dk)
        if _fold(kw) in pushed_keys:
            continue                        # đã push rồi — draft cũ không đếm đôi
        rows.append({"keyword": kw, "url": "", "clicks": 0, "imps": 0, "gsc": False,
                     "aeo_hit": 0, "aeo_asked": 0, "submit": False,
                     "state": "draft", "status": _STATE_LABEL["draft"],
                     "advice": "chưa xuất bản — duyệt rồi push WP"})

    rows.sort(key=lambda r: (_STATE_ORDER.index(r["state"]),
                             -r["clicks"], -r["imps"], _fold(r["keyword"])))
    return rows


def count_states(rows: list) -> dict:
    counts = {k: 0 for k in _STATE_ORDER}
    for r in rows or []:
        counts[r["state"]] = counts.get(r["state"], 0) + 1
    return counts


def report_text(rows: list, stamp: str = "") -> str:
    if not rows:
        return ("Chưa có bài nào để báo cáo — tạo draft (--plan) rồi push WP "
                "(--wp-push); xem tiến độ: --plan-progress.")
    lines = ["== HIỆU QUẢ TỪNG BÀI VIẾT ==",
             f"GSC snapshot: {stamp or 'chưa fetch — chạy python main.py --gsc'}", "",
             f'{"Bài viết":<38}{"Clicks":>7}{"Impr":>7}  {"AEO":<10}{"Submit":<8}Trạng thái',
             "-" * 110]
    for r in rows:
        aeo = f'{r["aeo_hit"]}/{r["aeo_asked"]}' if r["aeo_asked"] else "chưa hỏi"
        sub = "đã" if r["submit"] else ("—" if r["url"] else "")
        clicks = str(r["clicks"]) if r["url"] else "—"
        imps = str(r["imps"]) if r["url"] else "—"
        lines.append(f'{r["keyword"][:36]:<38}{clicks:>7}{imps:>7}  {aeo:<10}{sub:<8}'
                     f'{r["status"]}')
        if r["url"]:
            lines.append(f'    {r["url"]}')
        if r["advice"]:
            lines.append(f'    ↳ {r["advice"]}')
    c = count_states(rows)
    parts = [f'{c[k]} {_STATE_LABEL[k]}' for k in _STATE_ORDER if c.get(k)]
    lines += ["", "Tổng: " + ", ".join(parts) + ".",
              "GSC = snapshot pages gần nhất (--gsc); Submit = URL đã vào state IndexNow "
              "(không có ngày từng URL); AEO = engine nhắc / đã hỏi theo từ khóa bài."]
    return "\n".join(lines)


def pages_stamp() -> str:
    """Key ngày của snapshot GSC cuối ('' = chưa fetch) — cho header report."""
    try:
        from utils.gsc_pages import _snapshot_pages
        return _snapshot_pages()[1]
    except Exception:
        return ""


def run_post_report_cli() -> int:
    print(report_text(build_post_rows(), pages_stamp()))
    return 0
