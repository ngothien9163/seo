# -*- coding: utf-8 -*-
"""utils/content_brief.py — F10h: `--content-brief "<kw>"` — brief trộn dữ liệu.

Viết bài không nên bắt đầu từ trang giấy trắng. Lệnh này dựng **brief** (một
file markdown cho người đọc, KHÔNG gọi Ollama, KHÔNG sinh bài) gộp mọi dữ liệu
repo đã có về từ khóa / cụm của nó:

1. **Cụm từ khóa** — kw thuộc cụm nào (build_clusters), members là góc phụ.
2. **SERP hiện tại** — lần check gần nhất: hạng + URL nếu kw đang theo dõi.
3. **GSC** — imps/clicks/CTR/vị trí 28 ngày (rows snapshot; khớp fold) + query
   gắn với kw (chứa token của kw) làm câu hỏi phụ/dự án bài.
4. **Content plan** — thuộc ngày nào trong plan 30 ngày (khớp fold).
5. **Gợi ý khâu viết** — trong output console, không tự sửa file nào.

Điểm khác --generate: --generate gọi Ollama ra DRAFT; --content-brief chỉ gói
nguyên liệu + câu hỏi thành một bộ bám để người viết (hoặc prompt sau) dùng.
Xuất ra console; `--save` ghi `data/<slug>/brief_<kw-slug>.md` (atomic).
"""
BRIEF_QUERY_LIMIT = 8      # tối đa N query hợp lệ liệt kê
RELATED_MIN_SHARE = 1      # query chứa ≥ 1 token riêng của kw mới là "liên quan"

def _fold_kw(value: str) -> str:
    """Fold không dấu — bản duy nhất của repo (plan_progress dùng cùng)."""
    from utils.plan_progress import _fold_kw
    return _fold_kw(value)

def _kw_tokens(value: str) -> list:
    from utils.audit_actions import _kw_tokens
    return _kw_tokens(value)

def build_brief(keyword: str, keywords: list, rank_checks: dict,
                gsc_rows: dict, plan_rows: list = None,
                clusters: list = None) -> dict:
    """{keyword, cluster, members, rank, gsc_self, gsc_related queries, plan_day, questions}.

    sources thuần: test truyền thẳng; CLI tự nạp (mỗi nguồn trong try/except).
    Mỗi nguồn trống tự nói 'không có' — hỏng nguồn không chết brief.
    """
    kw = str(keyword or "").strip()
    if not kw:
        return {}
    key = _fold_kw(kw)
    ktoks = _kw_tokens(kw)

    # 1. cụm (build_clusters từ đầu vào đã có sẵn trong keywords.json)
    cluster, members = "", []
    for c in (clusters or []):
        anchor = str(c.get("anchor") or "")
        allm = [anchor] + [str(m) for m in (c.get("members") or [])]
        if key and any(_fold_kw(m) == key for m in allm):
            cluster = anchor
            members = [m for m in allm if _fold_kw(m) != key]
            break

    # 2. rank: lần check gần nhất của kw (nếu kw đang được theo dõi)
    checks = rank_checks or {}
    stamps = sorted(checks.keys())
    rank = None
    if stamps:
        for s in reversed(stamps):
            entry = (checks[s] or {}).get(kw) or {}
            pos = entry.get("pos")
            if isinstance(pos, int):
                rank = {"pos": pos, "url": str(entry.get("url") or ""), "stamp": s}
                break

    # 3. GSC: row trực tiếp của kw + query liên quan (chứa ≥ RELATED_MIN_SHARE token của kw)
    gsc_self = (gsc_rows or {}).get(kw) or (gsc_rows or {}).get(key) or {}
    related = []
    for q, r in (gsc_rows or {}).items():
        qk = _fold_kw(str(q))
        qt = set(_kw_tokens(qk))
        if not qt or not (set(ktoks) & qt):
            continue
        if _fold_kw(str(q)) == key:
            continue   # chính kw đã lấy ở gsc_self
        related.append({"query": str(q),
                        "imps": int((r or {}).get("impressions") or 0),
                        "clicks": int((r or {}).get("clicks") or 0),
                        "position": float((r or {}).get("position") or 0.0)})
    related.sort(key=lambda r: (-r["imps"], r["query"]))
    related = related[:BRIEF_QUERY_LIMIT]

    # 4. plan: kw thuộc mục nào
    plan_day = None
    for it in (plan_rows or []):
        if _fold_kw(str(it.get("keyword") or "")) == key:
            plan_day = it.get("day")
            break

    return {"keyword": kw, "cluster": cluster, "members": members, "rank": rank,
            "gsc_self": gsc_self, "related": related, "plan_day": plan_day}


def brief_text(data: dict) -> str:
    if not data:
        return "  Từ khóa trống — dùng: python main.py --content-brief \"từ khóa\""
    kw = data["keyword"]
    lines = [f"  BRIEF — {kw}",
             "  " + "=" * 70]
    if data.get("cluster"):
        member_list = ", ".join(data["members"][:5]) if data["members"] \
                       else "(cụm 1 người — không có member)"
        lines.append(f"  Cụm: anchor \"{data['cluster']}\" — góc phụ: {member_list}")
    else:
        lines.append("  Cụm: kw đơn độc — không có member, viết bài riêng")
    rank = data.get("rank")
    if rank:
        lines.append(f"  SERP hiện tại: hạng {rank['pos']}"
                     + (f" ({rank['url']})" if rank["url"] else "")
                     + f" — lần check {rank['stamp']}")
    else:
        lines.append("  SERP hiện tại: kw chưa được theo dõi (--gsc-add-keyword để thêm)")
    g = data.get("gsc_self") or {}
    if g.get("impressions"):
        lines.append(f"  GSC 28 ngày: {int(g.get('impressions', 0))} imps, "
                     f"{int(g.get('clicks', 0))} clicks, CTR "
                     f"{float(g.get('ctr', 0)) * 100:.1f}%, vị trí trung bình "
                     f"{float(g.get('position', 0)):,.1f}")
    else:
        lines.append("  GSC 28 ngày: chưa có row khớp — Google chưa phơi nhiều cho kw")
    rel = data.get("related") or []
    if rel:
        lines.append(f"  Query liên quan Google đang phơi ({len(rel)}):")
        for r in rel:
            lines.append(f'    · "{r["query"]}"  {r["imps"]} imps, vị trí {r["position"]:,.1f}')
    if data.get("plan_day") is not None:
        lines.append(f"  Content plan: thuộc ngày {data['plan_day']} — "
                     f"--generate --day {data['plan_day']}")
    lines.append("  " + "=" * 70)
    lines.append("  Brief này chỉ xếp nguyên liệu — dàn ý/bài viết viết ra sao là quyết định của writer.")
    return "\n".join(lines)


def save_brief(text: str, keyword: str, base_dir: str = None) -> str:
    """Ghi `brief_<kw-slug>.md` vào data/<slug>/ — atomic, trả đường path."""
    import os
    d = base_dir or _site_data_dir()
    os.makedirs(d, exist_ok=True)
    from utils.content_prompts import slugify
    path = os.path.join(d, f"brief_{slugify(keyword)}.md")
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
    return path


def _site_data_dir() -> str:
    import utils.site_paths as sp
    return sp._site_data_dir()


def run_content_brief_cli(keyword: str = "", save_to_disk: bool = False) -> int:
    """`--content-brief "<kw>"`: brief trộn dữ liệu, không gọi Ollama."""
    import config.settings as cfg
    from utils.gsc_client import _load_history, latest_gsc_rows
    from utils.keyword_groups import build_clusters
    from utils.plan_progress import build_progress
    from utils.alerts import _log

    kw = str(keyword or "").strip()
    if not kw:
        print('  Dùng: python main.py --content-brief "từ khóa"')
        return 2

    tracked = []
    try:
        from utils.keywords import load_keywords
        tracked = load_keywords()
    except Exception as e:
        _log(f"[Brief] keywords bỏ qua: {type(e).__name__}: {e}")
    rank_checks = (_load_history().get("checks") or {})
    rows = {}
    try:
        rows = latest_gsc_rows()
    except Exception as e:
        _log(f"[Brief] GSC bỏ qua: {type(e).__name__}: {e}")
    try:
        clusters = build_clusters(tracked)
    except Exception:
        clusters = []
    try:
        plan_rows = build_progress()
    except Exception:
        plan_rows = []

    data = build_brief(kw, tracked, rank_checks, rows, plan_rows, clusters)
    text = brief_text(data)
    print("=" * 104)
    print(f"  CONTENT BRIEF — {getattr(cfg, 'TARGET_URL', '') or '(chưa cấu hình site)'}")
    print("=" * 76)
    print(text)
    print("=" * 104)
    if save_to_disk:
        try:
            path = save_brief(text, kw)
            print(f"[Brief] Đã lưu: {path}")
        except Exception as e:
            _log(f"[Brief] Không lưu được: {type(e).__name__}: {e}")
    return 0
