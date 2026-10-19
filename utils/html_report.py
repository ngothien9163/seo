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
    """SERP: kw → (pos, delta, trend_text). Trống nếu chưa --rank lần nào."""
    try:
        from utils.rank_tracker import _load_history, delta_str, sparkline
    except Exception:
        return {}
    checks = _load_history().get("checks", {})
    if not checks:
        return {}
    keys = sorted(checks.keys())
    latest, prev = checks[keys[-1]], (checks[keys[-2]] if len(keys) >= 2 else {})
    rows = {}
    for kw in sorted(latest.keys()):
        cur = (latest.get(kw) or {}).get("pos")
        prv = (prev.get(kw) or {}).get("pos")
        trend = [(checks[k].get(kw) or {}).get("pos") for k in keys[-8:]]
        rows[kw] = {"pos": cur, "delta": delta_str(cur, prv),
                    "trend": sparkline(trend) if any(t is not None for t in trend) else "—"}
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
    return {"site": snap.get("site", ""), "range": f"{snap.get('start_date', '')} → "
                                                     f"{snap.get('end_date', '')}", "rows": rows}


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
    return {"rows": rows, "engines": engines, "sov": sov}


def collect() -> dict:
    """Gọi từng nguồn, mỗi nguồn tự nuốt lỗi (trống → section hướng dẫn)."""
    sections = {}
    for name, fn in (("rank", _rank_section), ("gsc", _gsc_section),
                     ("audit", _audit_section), ("backlink", _backlink_section),
                     ("aeo", _aeo_section), ("airobots", _airobots_section)):
        try:
            sections[name] = fn()
        except Exception:
            sections[name] = {}
    return sections


_SEV_CLASS = {"CAO": "sev-cao", "TRUNG BÌNH": "sev-trung", "THẤP": "sev-thap"}


def _render_rank(data: dict) -> str:
    if not data:
        return _empty_hint("SERP", "python main.py --rank")
    out = [f'<p class="meta">Lần check gần nhất: {escape(data["stamp"][:19].replace("T", " "))}</p>',
           "<table><tr><th>Từ khóa</th><th>Hạng</th><th>Δ</th><th>Xu hướng</th></tr>",
           "<tbody>"]
    for kw, r in data["rows"].items():
        pos = escape(str(r["pos"])) if r["pos"] is not None else f'<span class="dim">&gt;{getattr(cfg, "RANK_CHECK_DEPTH", 100)}</span>'
        out.append(f'<tr><td>{escape(kw)}</td><td class="num">{pos}</td>'
                   f'<td class="num">{escape(r["delta"])}</td>'
                   f'<td class="trend">{escape(r["trend"])}</td></tr>')
    out.append("</tbody></table>")
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
    (ai_robots_last.json, ghi mỗi lần chạy --ai-robots hoặc nút 🤖 GUI)."""
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
    return {"url": raw.get("url", ""), "status": raw.get("status"),
            "bots": bots}


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
    return "\n".join(out)


_RENDER = {"rank": _render_rank, "gsc": _render_gsc,
           "audit": _render_audit, "backlink": _render_backlink,
           "aeo": _render_aeo, "airobots": _render_airobots}

_TITLES = {"rank": "Xếp hạng Google (SERP)", "gsc": "Search Console (28 ngày)",
           "audit": "Audit on-page — findings gần nhất", "backlink": "Backlink đã đặt",
           "aeo": "AEO — AI trả lời có nhắc brand?",
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
    for name in ("rank", "gsc", "audit", "backlink", "aeo", "airobots"):
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
