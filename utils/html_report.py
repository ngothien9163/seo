# -*- coding: utf-8 -*-
"""utils/html_report.py — P1: báo cáo SEO gộp một file HTML, mở bằng browser.

Mỗi nguồn dữ liệu (SERP / GSC+AI / Audit / Backlink) là TÙY CHỌN: thiếu thì section
in hướng dẫn lấy, không bao giờ làm file trắng trang. Collect tách khỏi render —
collect là dict-of-dicts thuần data (test được không cần mạng), render escape mọi
giá trị qua html.escape (dữ liệu GSC/audit là text người khác viết, không tin).

File ghi atomic vào data/report.html (per-site khi đã migrate). Không JS, không
asset ngoài: một file duy nhất, email/USB đều mở được.
"""
import json
import os
import time
from html import escape

import config.settings as cfg
from utils import site_paths

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _report_path() -> str:
    return site_paths.per_site("report.html",
                               os.path.join(ROOT, getattr(cfg, "AUDIT_STATE_DIR", "data")))


def _rank_section() -> dict:
    """SERP: kw → (pos, delta, trend_text, src). Trống nếu chưa --rank lần nào.
    T29 — SERP không trả hạng (CAPTCHA) mà GSC có → pos = hạng GSC, src='GSC'
    (chỉ hiển thị, không ghi vào rank history — hạng SERP thật vẫn là nguồn thật)."""
    try:
        from utils.rank_tracker import _load_history, delta_str, sparkline
    except Exception:
        return {}
    checks = _load_history().get("checks", {})
    if not checks:
        return {}
    keys = sorted(checks.keys())
    latest, prev = checks[keys[-1]], (checks[keys[-2]] if len(keys) >= 2 else {})
    try:
        from utils.rank_tracker import gsc_positions
        gsc = gsc_positions()
    except Exception:
        gsc = {}
    rows = {}
    for kw in sorted(latest.keys()):
        cur = (latest.get(kw) or {}).get("pos")
        prv = (prev.get(kw) or {}).get("pos")
        trend = [(checks[k].get(kw) or {}).get("pos") for k in keys[-8:]]
        src = ""
        if cur is None and kw in gsc:
            cur, src = gsc[kw], "GSC"
        rows[kw] = {"pos": cur, "delta": delta_str(cur, prv) if src == "" else "—",
                    "trend": sparkline(trend) if any(t is not None for t in trend) else "—",
                    "src": src}
    return {"stamp": keys[-1], "rows": rows}


def _gsc_section() -> dict:
    """GSC 28 ngày + cột AI: kw → (clicks, impressions, position, ctr, ai)."""
    try:
        from utils.gsc_client import _load_history
    except Exception:
        return {}
    snaps = _load_history().get("snapshots", {})
    if not snaps:
        return {}
    snap = snaps[sorted(snaps.keys())[-1]]
    rows_raw = snap.get("rows", {})
    try:
        from utils.aeo import ai_matrix
        ai = ai_matrix()
    except Exception:
        ai = {}
    rows = {}
    for kw in sorted(rows_raw):
        r = rows_raw[kw] or {}
        per = ai.get(kw) or {}
        got = sum(1 for v in per.values() if v.get("mentioned"))
        rows[kw] = {"clicks": r.get("clicks", 0), "impressions": r.get("impressions", 0),
                    "position": r.get("position", 0.0), "ctr": r.get("ctr", 0.0),
                    "ai": (f"✓{got}/{len(per)}" if per else "—"), "ai_asked": bool(per)}
    out = {"site": snap.get("site", ""), "range": f"{snap.get('start_date', '')} → "
            f"{snap.get('end_date', '')}", "rows": rows}
    # T35 — trang nào đang gánh traffic: G-1 pages snapshot (snapshot cũ không có
    # field → ẩn khối, không nói dối "0 trang"). Gộp biến thể trailing slash sẵn.
    try:
        from utils.gsc_pages import _snapshot_pages
        from utils.post_report import _page_agg
        pages_raw, pg_stamp = _snapshot_pages()
        agg = _page_agg(pages_raw)
        if agg:
            top = sorted(agg.items(), key=lambda kv: (-kv[1]["clicks"], -kv[1]["imps"],
                                                      kv[0]))[:8]
            out["pages"] = {"stamp": pg_stamp, "n": len(agg), "shown": len(top),
                            "rows": [{"path": "/" + k.split("/", 1)[1] if "/" in k else "/",
                                      "clicks": v["clicks"], "imps": v["imps"]}
                                     for k, v in top]}
    except Exception:
        pass
    return out


def _audit_section() -> dict:
    """Findings audit gần nhất: severity → count, top findings (limit 12)."""
    try:
        from utils.site_auditor import load_last_audit
        findings = load_last_audit()
    except Exception:
        return {}
    if not findings:
        return {}
    sev_count = {}
    for f in findings:
        sev = str(f.get("severity", "THẤP"))
        sev_count[sev] = sev_count.get(sev, 0) + 1
    top = [{"severity": f.get("severity", "THẤP"), "rule": f.get("rule", ""),
            "url": f.get("url", ""), "detail": f.get("detail", "")}
           for f in findings[:12]]
    return {"total": len(findings), "sev_count": sev_count, "top": top}


def _backlink_section() -> dict:
    """Backlink đã đặt: (label_status, url, host, has_link, dofollow)."""
    try:
        from utils import backlinks as bl
        from utils.backlink_checker import state_rows, _status_label
        state = bl.load_state()
    except Exception:
        return {}
    if not state:
        return {}
    header, data = state_rows(state)
    rows = [{"status": row[0], "url": row[1], "host": row[2], "has_link": row[3] == "có",
             "dofollow": row[4] == "có"} for row in data]
    return {"rows": rows}


def _outreach_section() -> dict:
    """T32 — sổ liên hệ đặt link: đề xuất → đồng ý → đặt / mai một (0 request,
    chỉ đọc outreach.json). Trống → section hint hướng dẫn --outreach-add."""
    try:
        from utils.outreach import list_rows
        rows = list_rows()
    except Exception:
        return {}
    if not rows:
        return {}
    return {"rows": rows}


def _competitors_section() -> dict:
    """T27 — domain đối thủ hay xuất hiện top-10 SERP theo rank history (0 request).
    Đọc cùng nguồn --competitors (P2-1): top_urls từng mốc check."""
    try:
        from urllib.parse import urlparse
        import utils.competitors as comp
        from utils.rank_tracker import _load_history
    except Exception:
        return {}
    own = ""
    try:
        own = (urlparse(getattr(cfg, "TARGET_URL", "")).netloc or "").lower()
        own = own[4:] if own.startswith("www.") else own
    except ValueError:
        own = ""
    history = _load_history()
    per_kw, own, stamps = comp.competitor_history_from(history, own)
    overall = comp.overall_top(per_kw, own, 10)
    if not overall:
        return {}
    kws_with_data = len([1 for per in per_kw.values() if per])
    rows = [{"domain": d, "count": int(n)} for d, n in overall]
    per_kw_top = []
    for kw in sorted(per_kw):
        tops = comp.per_keyword_top(per_kw, kw, own, 3)
        if tops:
            per_kw_top.append({"keyword": kw,
                               "tops": [{"domain": d, "count": int(n)} for d, n in tops]})
    return {"rows": rows, "stamps": len(stamps), "keywords": kws_with_data,
            "per_kw": per_kw_top[:20], "own": own}


def _aeo_section() -> dict:
    """AEO (F9/T17): kw × engine — ✓/✗ nhắc brand, ngày đo. 0 request — chỉ đọc history.
    T23 thêm share-of-voice: đối thủ nhắc trong cùng câu trả lời (từ record mới)."""
    try:
        from utils.aeo import ai_matrix, sov_summary
        matrix = ai_matrix()
    except Exception:
        return {}
    if not matrix:
        return {}
    rows = {}
    for kw, per in matrix.items():
        rows[kw] = {
            engine: {"mark": "✓" if info.get("mentioned") else "✗",
                     "mentions": info.get("mentions", 0),
                     "date": info.get("date", ""),
                     "competitors": (info.get("competitors") or {})}
            for engine, info in per.items()
        }
    engines = sorted({e for per in matrix.values() for e in per})
    try:
        sov = sov_summary(matrix)
    except Exception:
        sov = {}
    # T31 — trend tuần: % câu trả lời được nhắc theo tuần (từ history, 0 request)
    try:
        from utils.aeo import load_history
        from utils.gui_charts import aeo_trend_series
        trend = aeo_trend_series(load_history())
    except Exception:
        trend = {}
    return {"rows": rows, "engines": engines, "sov": sov, "trend": trend}


def collect() -> dict:
    """Gọi từng nguồn, mỗi nguồn tự nuốt lỗi (trống → section hướng dẫn)."""
    sections = {}
    for name, fn in (("summary", _summary_section), ("rank", _rank_section),
                     ("gsc", _gsc_section), ("audit", _audit_section),
                     ("backlink", _backlink_section), ("outreach", _outreach_section),
                     ("aeo", _aeo_section), ("competitors", _competitors_section),
                     ("posts", _posts_section), ("airobots", _airobots_section)):
        try:
            sections[name] = fn()
        except Exception:
            sections[name] = {}
    return sections


def _summary_section() -> dict:
    """T34 — tóm tắt 30 giây: 8 số quan trọng nhất ghép từ nguồn các section đã có.
    Mỗi nguồn tự nuốt lỗi (thiếu → '—' ở render); không request mới nào."""
    out = {}
    # SERP — lần check gần nhất: bao nhiêu kw top-10, tốt nhất số mấy
    try:
        from utils.rank_tracker import _load_history
        checks = _load_history().get("checks") or {}
        if checks:
            last = sorted(checks.keys())[-1]
            rows = checks[last] or {}
            positions = [e.get("pos") for e in rows.values()
                         if isinstance(e, dict) and isinstance(e.get("pos"), int)]
            if positions:
                out["serp"] = {"stamp": last, "tracked": len(rows),
                               "top10": sum(1 for p in positions if p <= 10),
                               "best": min(positions), "measured": len(positions)}
    except Exception:
        pass
    # GSC — snapshot gần nhất: tổng clicks/imps + kỳ trước để so
    try:
        from utils.gsc_client import _load_history
        snaps = _load_history().get("snapshots") or {}
        if snaps:
            keys = sorted(snaps.keys())
            rows = (snaps[keys[-1]] or {}).get("rows") or {}
            clicks = sum(int((r or {}).get("clicks") or 0) for r in rows.values())
            imps = sum(int((r or {}).get("impressions") or 0) for r in rows.values())
            prev = None
            if len(keys) >= 2:
                prows = (snaps[keys[-2]] or {}).get("rows") or {}
                prev = {"clicks": sum(int((r or {}).get("clicks") or 0) for r in prows.values()),
                        "imps": sum(int((r or {}).get("impressions") or 0) for r in prows.values())}
            out["gsc"] = {"stamp": keys[-1], "clicks": clicks, "imps": imps, "prev": prev}
    except Exception:
        pass
    # AEO — % tuần này vs tuần trước (T31)
    try:
        from utils.aeo import load_history as aeo_load
        from utils.gui_charts import aeo_trend_series, trend_compare
        cur, prevw, n = trend_compare(aeo_trend_series(aeo_load()))
        if cur is not None:
            out["aeo"] = {"cur": cur, "prev": prevw, "weeks": n}
    except Exception:
        pass
    # Bài viết (T30) — đang kéo / lẻo / draft
    try:
        from utils.post_report import build_post_rows, count_states
        out["posts"] = count_states(build_post_rows())
    except Exception:
        pass
    # Outreach (T32) — đếm theo trạng thái
    try:
        from utils.outreach import list_rows
        c = {}
        for r in list_rows():
            c[r["state"]] = c.get(r["state"], 0) + 1
        out["outreach"] = c
    except Exception:
        pass
    # PageSpeed (T33) — đã đo bao nhiêu, bao nhiêu dưới ngưỡng
    try:
        from utils.pagespeed import posts_load, weak_posts
        out["pspeed"] = {"measured": len(posts_load()["urls"]),
                         "weak": len(weak_posts())}
    except Exception:
        pass
    # Backlink — sống / tổng
    try:
        from utils import backlinks as bl
        from utils.backlink_checker import state_rows
        state = bl.load_state()
        if state:
            _header, data = state_rows(state)
            out["backlink"] = {"total": len(data),
                               "alive": sum(1 for row in data
                                            if str(row[0]).startswith("Còn sống"))}
    except Exception:
        pass
    # Bot AI — bao nhiêu bị chặn / tổng bot đã biết
    try:
        from utils.ai_robots import robots_state_path
        with open(robots_state_path(), encoding="utf-8") as f:
            last_state = json.load(f)
        bots = [b for b in (last_state.get("bots") or []) if isinstance(b, dict)]
        out["airobots"] = {"total": len(bots),
                           "blocked": sum(1 for b in bots
                                          if b.get("status") == "blocked")}
    except Exception:
        pass
    return out


def _render_summary(data: dict) -> str:
    """T34 — bảng tóm tắt đầu report: mỗi dòng 1 nguồn, thiếu → '—' (không dùng
    class 'empty' — section này luôn hiện, không phải 'chưa lấy dữ liệu')."""
    out = ['<p class="meta">Tình hình nhanh ghép từ các section dưới — số chi tiết '
           "và lịch sử xem ở section tương ứng. 0 request mới.</p>",
           "<table><tr><th>Mảng</th><th>Hiện tại</th></tr><tbody>"]

    def row(name: str, value: str, cls: str = "") -> None:
        v = value or '<span class="dim">—</span>'
        out.append(f'<tr><td>{escape(name)}</td><td class="{cls}">{v}</td></tr>')

    serp = data.get("serp") or {}
    if serp:
        row("Xếp hạng (SERP)",
            f'{serp["top10"]}/{serp["measured"]} kw top-10, tốt nhất #{serp["best"]} '
            f'<span class="dim">(check {escape(str(serp["stamp"]))[:16].replace("T", " ")})</span>',
            "ok" if serp["top10"] else "warn")
    else:
        row("Xếp hạng (SERP)", "", "dim")
    gsc = data.get("gsc") or {}
    if gsc:
        delta = ""
        prev = gsc.get("prev") or {}
        if prev:
            dc = gsc["clicks"] - prev.get("clicks", 0)
            di = gsc["imps"] - prev.get("imps", 0)
            delta = (f' <span class="dim">(kỳ trước {prev.get("clicks", 0)}/'
                     f'{prev.get("imps", 0)}; Δ {dc:+d}/{di:+d})</span>')
        row("Search Console (28 ngày)",
            f'{gsc["clicks"]} clicks / {gsc["imps"]} imps{delta}',
            "ok" if gsc["clicks"] else "")
    else:
        row("Search Console (28 ngày)", "", "dim")
    aeo = data.get("aeo") or {}
    if aeo:
        word = "tăng" if (aeo.get("cur") or 0) > (aeo.get("prev") or 0) else \
               "giảm" if (aeo.get("cur") or 0) < (aeo.get("prev") or 0) else "đứng yên"
        row("AEO (AI nhắc brand)",
            f'{aeo["cur"]}% câu trả lời được nhắc tuần này '
            f'<span class="dim">(tuần trước {aeo.get("prev")}% — {word})</span>',
            "ok" if (aeo.get("cur") or 0) >= (aeo.get("prev") or 0) else "warn")
    else:
        row("AEO (AI nhắc brand)", "", "dim")
    posts = data.get("posts") or {}
    if posts:
        bits = [f'{posts.get(k, 0)} {lab}' for k, lab in
                (("pull", "đang kéo"), ("show", "hiển thị"), ("dead", "lẻo"),
                 ("nodata", "chưa có GSC"), ("draft", "draft")) if posts.get(k)]
        row("Bài viết (T30)", " · ".join(bits) if bits else "", "")
    else:
        row("Bài viết (T30)", "", "dim")
    outreach = data.get("outreach") or {}
    if outreach:
        bits = [f'{outreach.get(k, 0)} {lab}' for k, lab in
                (("proposed", "chờ phản hồi"), ("agreed", "chờ đặt"),
                 ("placed", "đã đặt"), ("dead", "mai một")) if outreach.get(k)]
        row("Outreach (T32)", " · ".join(bits) if bits else "", "")
    else:
        row("Outreach (T32)", "", "dim")
    pspeed = data.get("pspeed") or {}
    if pspeed.get("measured"):
        weak = pspeed.get("weak") or 0
        row("PageSpeed (T33)",
            f'{pspeed["measured"]} bài đã đo, {weak} bài dưới ngưỡng'
            f'<span class="dim"> (--pagespeed-posts)</span>',
            "warn" if weak else "ok")
    else:
        row("PageSpeed (T33)", "", "dim")
    backlink = data.get("backlink") or {}
    if backlink:
        row("Backlink",
            f'{backlink["alive"]}/{backlink["total"]} link còn sống',
            "ok" if backlink["alive"] else "warn")
    else:
        row("Backlink", "", "dim")
    airobots = data.get("airobots") or {}
    if airobots:
        row("Bot AI (robots.txt)",
            f'{airobots["blocked"]}/{airobots["total"]} bot bị chặn',
            "warn" if airobots.get("blocked") else "ok")
    else:
        row("Bot AI (robots.txt)", "", "dim")
    out.append("</tbody></table>")
    return "\n".join(out)


_SEV_CLASS = {"CAO": "sev-cao", "TRUNG BÌNH": "sev-trung", "THẤP": "sev-thap"}


def _render_rank(data: dict) -> str:
    if not data:
        return _empty_hint("SERP", "python main.py --rank")
    gsc_used = 0
    out = [f'<p class="meta">Lần check gần nhất: {escape(data["stamp"][:19].replace("T", " "))}</p>',
           "<table><tr><th>Từ khóa</th><th>Hạng</th><th>Δ</th><th>Xu hướng</th></tr>",
           "<tbody>"]
    for kw, r in data["rows"].items():
        if r["pos"] is not None:
            pos = escape(str(r["pos"]))
            if r.get("src") == "GSC":
                # T29 — hạng trung bình GSC 28 ngày (SERP lần check bị CAPTCHA)
                pos = f'~{pos} <span class="dim">(GSC)</span>'
                gsc_used += 1
        else:
            pos = f'<span class="dim">&gt;{getattr(cfg, "RANK_CHECK_DEPTH", 100)}</span>'
        out.append(f'<tr><td>{escape(kw)}</td><td class="num">{pos}</td>'
                   f'<td class="num">{escape(r["delta"])}</td>'
                   f'<td class="trend">{escape(r["trend"])}</td></tr>')
    out.append("</tbody></table>")
    if gsc_used:
        out.append(f'<p class="meta">SERP không trả hạng cho {gsc_used} từ khóa (CAPTCHA) — '
                   "đang hiển thị hạng trung bình GSC 28 ngày, nhãn ~(GSC). "
                   "Chạy lại --rank khi bớt CAPTCHA để có hạng thật.</p>")
    return "\n".join(out)


def _render_gsc(data: dict) -> str:
    if not data:
        return _empty_hint("Search Console",
                           "Setup: docs/SETUP_GSC.md — lấy lần đầu: python main.py --gsc")
    out = [f'<p class="meta">{escape(data["site"])} · {escape(data["range"])}</p>',
           "<table><tr><th>Từ khóa</th><th>AI</th><th>Clicks</th><th>Hiện</th>"
           "<th>Vị trí TB</th><th>CTR</th></tr><tbody>"]
    for kw, r in data["rows"].items():
        out.append(f'<tr><td>{escape(kw)}</td><td>{escape(r["ai"])}</td>'
                   f'<td class="num">{r["clicks"]}</td><td class="num">{r["impressions"]}</td>'
                   f'<td class="num">{r["position"]:.1f}</td><td class="num">{r["ctr"] * 100:.1f}%</td></tr>')
    out.append("</tbody></table>")
    # T35 — trang nào đang gánh traffic: nhiều query cùng đấm 1 trang hay service
    # page nào thật sự được bấm — bảng path gọn, không in URL nguyên si dài
    pg = data.get("pages") or {}
    if pg.get("rows"):
        out.append(f'<p class="meta">Trang nào đang gánh traffic — GSC snapshot '
                   f'{escape(str(pg.get("stamp") or ""))}, gộp biến thể trailing slash; '
                   "GSC không trả page cho query chưa ai phơi, số dưới có thể thấp hơn tổng lượt phơi.</p>")
        out.append('<table><tr><th>Trang</th><th>Clicks</th><th>Hiện</th>'
                   "<th>CTR</th></tr><tbody>")
        for r in pg["rows"]:
            ctr = (r["clicks"] / r["imps"] * 100) if r["imps"] else 0.0
            out.append(f'<tr><td class="url">{escape(r["path"])}</td>'
                       f'<td class="num">{r["clicks"]}</td><td class="num">{r["imps"]}</td>'
                       f'<td class="num">{ctr:.1f}%</td></tr>')
        out.append("</tbody></table>")
        if (pg.get("n") or 0) > (pg.get("shown") or 0):
            out.append(f'<p class="meta dim">…và {pg["n"] - pg["shown"]} trang nữa '
                       "(clicks/imps thấp hơn) — đủ 8 hàng là đủ nhìn.</p>")
    return "\n".join(out)


def _render_audit(data: dict) -> str:
    if not data:
        return _empty_hint("Audit on-page", "python main.py --audit")
    chips = " ".join(f'<span class="chip {escape(_SEV_CLASS.get(s, "sev-thap"))}">'
                     f'{escape(s)}: {n}</span>' for s, n in sorted(data["sev_count"].items()))
    out = [f'<p class="meta">Tổng {data["total"]} finding</p>', chips,
           "<table><tr><th>Mức</th><th>Rule</th><th>Trang</th><th>Chi tiết</th></tr><tbody>"]
    for f in data["top"]:
        out.append(f'<tr><td><span class="chip {escape(_SEV_CLASS.get(f["severity"], "sev-thap"))}">'
                   f'{escape(f["severity"])}</span></td><td>{escape(f["rule"])}</td>'
                   f'<td class="url">{escape(f["url"])}</td><td>{escape(f["detail"])}</td></tr>')
    out.append("</tbody></table>")
    return "\n".join(out)


def _render_backlink(data: dict) -> str:
    if not data:
        return _empty_hint("Backlink",
                           'python main.py --backlink-add "https://site-nguoi-khac/bai-co-link" '
                           '→ python main.py --backlink-check')
    out = ["<table><tr><th>Trạng thái</th><th>URL</th><th>Host</th><th>Còn link?</th>"
           "<th>Dofollow?</th></tr><tbody>"]
    alive = sum(1 for r in data["rows"] if r["status"].startswith("Còn sống"))
    for r in data["rows"]:
        cls = "ok" if r["status"].startswith("Còn sống") else "warn" if ("Chuyển hướng" in r["status"] or "Bị chặn" in r["status"]) else "bad"
        out.append(f'<tr><td class="{cls}">{escape(r["status"])}</td>'
                   f'<td class="url">{escape(r["url"])}</td><td>{escape(r["host"])}</td>'
                   f'<td>{"✓" if r["has_link"] else "—"}</td><td>{"✓" if r["dofollow"] else "—"}</td></tr>')
    out.append("</tbody></table>")
    out.append(f'<p class="meta">{alive}/{len(data["rows"])} link còn sống.</p>')
    return "\n".join(out)


def _render_outreach(data: dict) -> str:
    """T32 — sổ outreach: đề xuất → đồng ý → đặt / mai một; ngày chờ + ghi chú."""
    if not data:
        return _empty_hint("Sổ outreach",
                           'python main.py --outreach-add "URL-bài-of-site-người-ta" '
                           '--outreach-kw "anchor" (chỉ ghi sổ + nhắc, không tự liên hệ)')
    out = ['<p class="meta">Sổ liên hệ đặt link — việc liên hệ làm tay ngoài tool; '
           "tại đây ghi trạng thái để báo cáo ngày nhắc follow-up đúng chu kỳ.</p>",
           "<table><tr><th>Trạng thái</th><th>Trang đích</th><th>Anchor</th>"
           "<th>Chờ</th><th>Ghi chú</th></tr><tbody>"]
    cls_of = {"proposed": "warn", "agreed": "", "placed": "ok", "dead": "bad"}
    for r in data["rows"]:
        note = escape(r["note"]) if r["note"] else ""
        stage = (f'{r["days"]} ngày' if r["days"] > 0 else ("hôm nay" if r["days"] == 0 else ""))
        addr = (f'{escape(r["title"]) if r["title"] else ""}'
                f'<br><span class="url">{escape(r["url"])}</span>')
        out.append(f'<tr><td class="{cls_of.get(r["state"], "")}">{escape(r["status"])}</td>'
                   f'<td>{addr}</td><td>{escape(r["kw"] or "—")}</td>'
                   f'<td class="num">{stage or "—"}</td><td>{note or "—"}</td></tr>')
    out.append("</tbody></table>")
    c = {}
    for r in data["rows"]:
        c[r["state"]] = c.get(r["state"], 0) + 1
    parts = [f"{c[k]} {lab}" for k, lab in
             (("proposed", "chờ phản hồi"), ("agreed", "chờ đặt"), ("placed", "đã đặt"),
              ("dead", "mai một")) if c.get(k)]
    if parts:
        out.append('<p class="meta">Tổng: ' + escape(", ".join(parts)) + ".</p>")
    out.append('<p class="meta dim">Set "placed" xong chạy '
               '<code>python main.py --backlink-add "URL"</code> để hệ verify theo dõi '
               "còn sống/dofollow — sổ này không tự bấm gì thay bạn.</p>")
    return "\n".join(out)


def _render_aeo(data: dict) -> str:
    """AEO: hàng mỗi từ khóa, cột mỗi engine đã hỏi — engine chưa hỏi không hiện cột."""
    if not data:
        return _empty_hint("AEO (AI nhắc brand)",
                           "hỏi AI theo 1 từ khóa → python main.py --aeo-check answer.txt "
                           "--aeo-keyword \"kw\" (docs/USE_AEO.md)")
    engines = data["engines"]
    asked = sum(1 for per in data["rows"].values() for _ in per.values())
    hit = sum(1 for per in data["rows"].values() for v in per.values() if v["mark"] == "✓")
    out = [f'<p class="meta">Đã hỏi {asked} cặp (từ khóa × engine) — {hit} lần engine nhắc brand. '
           f"Dán tay qua tab 📢 AI Nói Gì hoặc --aeo-check.</p>",
           "<table><tr><th>Từ khóa</th>" + "".join(f"<th>{escape(e)}</th>" for e in engines) +
           "</tr><tbody>"]
    for kw in sorted(data["rows"]):
        cells = []
        for e in engines:
            info = data["rows"][kw].get(e)
            if info is None:
                cells.append('<td class="dim">—</td>')
            else:
                cls = "ok" if info["mark"] == "✓" else "bad"
                n = f' <span class="dim">x{info["mentions"]}</span>' if info["mentions"] > 1 else ""
                cells.append(f'<td class="{cls}">{info["mark"]}{n}</td>')
        out.append(f"<tr><td>{escape(kw)}</td>" + "".join(cells) + "</tr>")
    out.append("</tbody></table>")
    out.append('<p class="meta">✓ = engine nhắc brand, ✗ = không nhắc, — = chưa hỏi. '
               "1 bản ghi/ngày/từ khóa/engine (dán lại là cập nhật).</p>")
    # T31 — trend theo tuần: 1 dòng so 2 tuần có dữ liệu cuối (≥2 tuần mới hiện)
    try:
        from utils.gui_charts import trend_compare, trend_words
        cur, prev, n = trend_compare(data.get("trend"))
        if cur is not None and prev is not None:
            out.append(f'<p class="meta">📈 Trend: tuần này {cur}% câu trả lời được nhắc brand '
                       f"(tuần trước {prev}% — {trend_words(cur, prev)}; "
                       f"{n} tuần có dữ liệu trong 8 tuần gần nhất).</p>")
    except Exception:
        pass
    # T23 share-of-voice: bảng nhỏ dưới — AI nhắc ai trong cùng câu trả lời
    sov = (data.get("sov") or {}).get("own") or {}
    if sov.get("asked"):
        own_total, own_hit = int(sov.get("asked", 0)), int(sov.get("hit", 0))
        out.append('<p class="meta">Share-of-voice (' + str(own_total) +
                   f" câu có dữ liệu): mình được nhắc {own_hit}/"
                   f"{own_total} ({int(own_hit * 100.0 / own_total) if own_total else 0}%).</p>")
        comps = (data.get("sov") or {}).get("competitors") or {}
        if comps:
            out.append("<table><tr><th>Đối thủ</th><th>Được nhắc (câu)</th>"
                       "<th>Cùng mình (câu)</th></tr><tbody>")
            for name, c in comps.items():
                out.append(f"<tr><td>{escape(name)}</td><td class=\"num\">{c.get('hit', 0)}"
                           f"</td><td class=\"num\">{c.get('co', 0)}</td></tr>")
            out.append("</tbody></table>")
        else:
            out.append('<p class="meta dim">Chưa khai báo AEO_COMPETITORS trong settings — '
                       "không so đối thủ nào.</p>")
    return "\n".join(out)


def _empty_hint(title: str, hint: str) -> str:
    return (f'<p class="empty">Chưa có dữ liệu {escape(title.lower())}. '
            f'<code>{escape(hint)}</code></p>')


def _airobots_section() -> dict:
    """T25 — bot AI nào bị robots.txt chặn? 0 request: đọc file state T22
    (ai_robots_last.json, ghi mỗi lần chạy --ai-robots hoặc nút 🤖 GUI).
    T28 — thêm drift: mốc history trước mốc hiện tại có khác không."""
    try:
        from utils import ai_robots as ar
    except Exception:
        return {}
    path = ar.robots_state_path()
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return {}
    bots = [b for b in (raw.get("bots") or []) if isinstance(b, dict) and b.get("bot")]
    if not bots:
        return {}
    drift = []
    try:
        history = ar.load_history()
        drift_rows, _snap = ar.drift_lines_for_html(history, bots)
        drift = [{"bot": b, "old": o, "new": n} for b, o, n in drift_rows]
    except Exception:
        drift = []
    return {"url": raw.get("url", ""), "status": raw.get("status"),
            "bots": bots, "drift": drift}


def _render_airobots(data: dict) -> str:
    if not data:
        return _empty_hint("bot AI bị chặn",
                           "python main.py --ai-robots "
                           "(1 request — chỉ báo cáo, tool không sửa robots.txt)")
    blocked = [b for b in data["bots"] if b.get("status") == "blocked"]
    head = (f'<p class="meta">robots.txt HTTP {escape(str(data["status"]))} — '
            f'{len(blocked)}/{len(data["bots"])} bot AI bị chặn. '
            "Tool chỉ báo cáo — KHÔNG tự sửa robots.txt.</p>")
    out = [head,
           "<table><tr><th>Bot AI</th><th>Trạng thái</th><th>Đường dẫn bị chặn</th></tr><tbody>"]
    for b in data["bots"]:
        st = str(b.get("status") or "")
        if st == "blocked":
            cls, label = "bad", "CHẶN"
        elif st == "explicit":
            cls, label = "ok", "Cho phép (khai rõ)"
        else:
            cls, label = "dim", "Mặc định (không đề cập — được vào)"
        paths = ", ".join(str(p) for p in (b.get("paths") or [])[:6])
        out.append(f'<tr><td>{escape(str(b.get("bot") or ""))}</td>'
                   f'<td class="{cls}">{escape(label)}</td>'
                   f'<td class="url">{escape(paths or "—")}</td></tr>')
    out.append("</tbody></table>")
    if data.get("url"):
        out.append(f'<p class="meta dim">Trạng thái của robots.txt: {escape(str(data["url"]))}</p>')
    # T28 — drift: khác biệt so mốc trước (nếu có)
    for d in (data.get("drift") or []):
        out.append(f'<p class="meta"><strong>⚠️ Thay đổi so lần check trước — '
                   f'{escape(str(d["bot"]))}:</strong> {escape(str(d["old"]))} → '
                   f'{escape(str(d["new"]))}.</p>')
    return "\n".join(out)


def _render_competitors(data: dict) -> str:
    """T27 — bảng domain đối thủ thường xuất hiện top-10 SERP + top 3 theo từ khóa."""
    if not data:
        return _empty_hint("domain đối thủ trên SERP",
                           "python main.py --rank (≥ 2 lần — top_urls ghi trong history) "
                           '→ python main.py --competitors xem chi tiết')
    head = (f'<p class="meta">{escape(str(data.get("keywords", 0)))} từ khóa × '
            f'{escape(str(data.get("stamps", 0)))} mốc có dữ liệu SERP — đếm tần suất '
            "XUẤT HIỆN trên top-10, không khẳng định ai 'chiếm hạng'.</p>")
    out = [head,
           "<table><tr><th>Domain đối thủ</th><th>Lần xuất hiện</th>"
           "<th>Xuất hiện nhiều ở từ khóa</th></tr><tbody>"]
    kw_of = {}
    for entry in (data.get("per_kw") or []):
        for t in entry.get("tops", []):
            kw_of.setdefault(t["domain"], []).append(
                f'{entry["keyword"]} ({t["count"]})')
    own = str(data.get("own") or "")
    for r in (data.get("rows") or []):
        kws = ", ".join(kw_of.get(r["domain"], [])[:3]) or "—"
        out.append(f'<tr><td>{escape(r["domain"])}'
                   + (' <span class="dim">(mình)</span>' if r["domain"] == own and own else "")
                   + f'</td><td class="num">{r["count"]}</td>'
                   f'<td>{escape(kws)}</td></tr>')
    out.append("</tbody></table>")
    out.append('<p class="meta dim">Chỉ 10 domain xuất hiện nhiều nhất; chi tiết theo '
               "từ khóa: python main.py --competitors.</p>")
    return "\n".join(out)


def _posts_section() -> dict:
    """T30 — hiệu quả từng bài viết: ghép wp_pushed + GSC pages + AEO + IndexNow.
    0 request mới; nguồn nào hỏng builder tự bỏ — trống bài → section hint."""
    try:
        from utils.post_report import build_post_rows, count_states
        rows = build_post_rows()
    except Exception:
        return {}
    if not rows:
        return {}
    try:
        from utils.post_report import pages_stamp
        stamp = pages_stamp()
    except Exception:
        stamp = ""
    return {"rows": rows, "stamp": stamp, "counts": count_states(rows)}


def _render_posts(data: dict) -> str:
    """T30 — bảng bài viết: Clicks/Impr khớp URL GSC, AEO theo từ khóa, advice."""
    if not data:
        return _empty_hint("Hiệu quả bài viết",
                           "push bài (--wp-push) rồi: python main.py --post-report "
                           "(ghép GSC pages + AEO + IndexNow)")
    out = [f'<p class="meta">GSC snapshot: {escape(data.get("stamp") or "chưa fetch — chạy --gsc")}. '
           "Ghép bài đã push WP (wp_pushed.json) với GSC pages + AEO + IndexNow — 0 request mới.</p>",
           "<table><tr><th>Bài viết</th><th>URL</th><th>Clicks</th><th>Impr</th>"
           "<th>AEO</th><th>Submit</th><th>Trạng thái</th></tr><tbody>"]
    cls_of = {"pull": "ok", "show": "warn", "dead": "bad", "nodata": "dim", "draft": "dim"}
    for r in data["rows"]:
        aeo = f'{r["aeo_hit"]}/{r["aeo_asked"]}' if r["aeo_asked"] else '<span class="dim">—</span>'
        sub = "✓" if r["submit"] else "—"
        url_cell = (f'<span class="url">{escape(r["url"])}</span>'
                    if r["url"] else '<span class="dim">—</span>')
        clicks = str(r["clicks"]) if r["url"] else "—"
        imps = str(r["imps"]) if r["url"] else "—"
        st = escape(r["status"])
        if r.get("advice"):
            st += f'<br><span class="dim">↳ {escape(r["advice"])}</span>'
        out.append(f'<tr><td>{escape(r["keyword"])}</td><td>{url_cell}</td>'
                   f'<td class="num">{clicks}</td><td class="num">{imps}</td>'
                   f'<td>{aeo}</td><td>{sub}</td>'
                   f'<td class="{cls_of.get(r["state"], "")}">{st}</td></tr>')
    out.append("</tbody></table>")
    c = data.get("counts") or {}
    parts = [f"{c[k]} {lab}" for k, lab in
             (("pull", "đang kéo"), ("show", "hiển thị chưa bấm"), ("dead", "lẻo"),
              ("nodata", "chưa có dữ liệu GSC"), ("draft", "draft chờ duyệt"))
             if c.get(k)]
    if parts:
        out.append('<p class="meta">Tổng: ' + escape(", ".join(parts)) + ".</p>")
    out.append('<p class="meta dim">Clicks/Impr = GSC pages snapshot gần nhất khớp permalink WP '
               "(bỏ query/trailing slash) hoặc slug từ khóa; Submit = URL đã vào state IndexNow "
               "— gõ --indexnow để submit URL mới. Bài mới chưa có GSC là bình thường "
               "(cần vài ngày); khớp sai slug thì sửa link trong wp_pushed.json.</p>")
    return "\n".join(out)


_RENDER = {"summary": _render_summary,
           "rank": _render_rank, "gsc": _render_gsc,
           "audit": _render_audit, "backlink": _render_backlink,
           "outreach": _render_outreach,
           "aeo": _render_aeo, "competitors": _render_competitors,
           "posts": _render_posts, "airobots": _render_airobots}

_TITLES = {"summary": "Tóm tắt — tình hình nhanh",
           "rank": "Xếp hạng Google (SERP)", "gsc": "Search Console (28 ngày)",
           "audit": "Audit on-page — findings gần nhất", "backlink": "Backlink đã đặt",
           "outreach": "Sổ outreach — xin đặt link",
           "aeo": "AEO — AI trả lời có nhắc brand?",
           "competitors": "Domain đối thủ thường xuất hiện (SERP top-10)",
           "posts": "Hiệu quả từng bài viết (GSC × WP × AEO × IndexNow)",
           "airobots": "Bot AI có vào được site? (robots.txt)"}

_CSS = (":root{--ink:#1f2430;--line:#e3e6ee;--soft:#f6f7fb;--cao:#b3261e;"
        "--trung:#b26a00;--thap:#5f6b7a;--ok:#1e7d40;--warn:#b26a00;--bad:#b3261e}"
        "*{box-sizing:border-box}body{font:14px/1.45 system-ui,Segoe UI,Roboto,sans-serif;"
        "color:var(--ink);margin:0;background:#fff}"
        "header{padding:20px 24px;border-bottom:2px solid var(--ink)}"
        "h1{margin:0;font-size:20px}.sub{color:#5f6b7a;font-size:12px;margin-top:4px}"
        "main{padding:8px 24px 32px}section{margin:22px 0;border:1px solid var(--line);"
        "border-radius:8px;overflow:hidden}h2{margin:0;padding:10px 14px;font-size:14px;"
        "background:var(--soft);border-bottom:1px solid var(--line)}"
        "section>div{padding:12px 14px}table{width:100%;border-collapse:collapse}"
        "th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;"
        "vertical-align:top}th{background:var(--soft);font-weight:600;white-space:nowrap}"
        "td.num{text-align:right;font-variant-numeric:tabular-nums}"
        ".trend{font-variant-numeric:tabular-nums}.dim{color:#9aa3b2}"
        ".meta{color:#5f6b7a;font-size:12px;margin:0 0 10px}"
        ".url{font-family:Consolas,monospace;font-size:12px;word-break:break-all}"
        ".chip{display:inline-block;padding:1px 8px;border-radius:10px;font-size:11px;"
        "font-weight:600;background:var(--soft);color:var(--thap)}"
        ".sev-cao{background:#fbe9e7;color:var(--cao)}.sev-trung{background:#fff3e0;color:var(--trung)}"
        ".sev-thap{background:var(--soft)}.badge-ok{color:var(--ok)}.badge-warn{color:var(--warn)}"
        ".badge-bad{color:var(--bad)}td.ok{color:var(--ok)}td.warn{color:var(--warn)}td.bad{color:var(--bad)}"
        ".empty{color:#5f6b7a}code{background:var(--soft);padding:1px 5px;border-radius:4px;"
        "font-size:12px}")


def render(sections: dict) -> str:
    """HTML hoàn chỉnh. Mọi text đi qua html.escape — kể cả phần hướng dẫn."""
    domain = site_paths.site_domain()
    stamp = time.strftime("%Y-%m-%d %H:%M")
    parts = ["<!DOCTYPE html>", '<html lang="vi"><head><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width, initial-scale=1">',
             "<title>Báo cáo SEO — ", escape(domain or "site"), "</title>",
             f"<style>{_CSS}</style></head><body>",
             "<header><h1>Báo cáo SEO — ", escape(domain or "(chưa cấu hình site)"),
             "</h1>", f'<p class="sub">Xuất {escape(stamp)} — python main.py --html-report</p>',
             "</header><main>"]
    for name in ("summary", "rank", "gsc", "audit", "backlink", "outreach", "aeo",
                 "competitors", "posts", "airobots"):
        body = _RENDER[name](sections.get(name) or {})
        parts.append(f"<section><h2>{escape(_TITLES[name])}</h2><div>{body}</div></section>")
    parts.append("</main></body></html>")
    return "\n".join(parts)


def run_html_report_cli(path: str = "") -> int:
    """`--html-report [path]` — ghi 1 file, trả về 0. Kể cả khi mọi nguồn trống."""
    out = path or _report_path()
    folder = os.path.dirname(out)
    if folder:
        os.makedirs(folder, exist_ok=True)
    html = render(collect())
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    os.replace(tmp, out)
    print(f"[HTML] Đã ghi {out}\n[HTML] Mở bằng: start {out}")
    return 0
