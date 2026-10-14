# -*- coding: utf-8 -*-
"""content/generator.py — F8 pipeline: plan → outline → draft → file markdown.

Client Ollama tiêm qua tham số `client` (mặc định = utils.ollama_client), nên test
chạy offline không cần `ollama serve`. Tool CHỈ sinh bản nháp, không tự đăng.
"""
import os
from datetime import datetime

import config.settings as cfg
from utils import content_prompts as cp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def drafts_dir():
    """Thư mục của bài nháp — đọc cfg lúc gọi (một điểm duy nhất, hedge F10)."""
    return os.path.join(ROOT, cfg.CONTENT_DRAFTS_DIR.replace("/", os.sep))


def _client():
    import utils.ollama_client as oc
    return oc


def plan_item(day=None, keyword=""):
    """Tra mục trong DEFAULT_30D_PLAN khớp `day` (ngày) hoặc `keyword` (fold không dấu).
    Không tìm thấy / cả hai trống → None."""
    try:
        from content.planner import DEFAULT_30D_PLAN as PLAN
    except Exception:
        return None
    if day is not None:
        for it in PLAN:
            if it.get("day") == day:
                return it
        return None
    if keyword:
        want = cp._fold(keyword)
        for it in PLAN:
            if cp._fold(it.get("keyword", "")) == want:
                return it
    return None


def _unique_path(out_dir, slug):
    """<slug>-<YYYYMMDD-HHMMSS>.md, trùng thì thêm -1, -2 → không bao giờ ghi đè."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(out_dir, "%s-%s.md" % (slug, stamp))
    n = 1
    while os.path.exists(path):
        path = os.path.join(out_dir, "%s-%s-%d.md" % (slug, stamp, n))
        n += 1
    return path


def render_article(keyword, outline_and_draft, item, out_dir=None):
    """Ghép frontmatter + draft và ghi file UTF-8 KHÔNG BOM (atomic). Trả (path, text)."""
    _outline, draft = outline_and_draft
    today = datetime.now().strftime("%Y-%m-%d")
    meta = {
        "keyword": keyword,
        "topic": (item or {}).get("target", "") or "",
        "type": (item or {}).get("type", "blog") or "blog",
        "date": today,
        "model": cfg.CONTENT_MODEL,
    }
    doc = cp.assemble(cp.build_frontmatter(meta), draft or "")
    out_dir = out_dir or drafts_dir()
    os.makedirs(out_dir, exist_ok=True)
    path = _unique_path(out_dir, cp.slugify(keyword))
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(doc)
    os.replace(tmp, path)
    return path, doc


def generate_article(keyword="", day=None, client=None, out_dir=None, dry_run=False):
    """Pipeline đầy đủ. Trả (path|None, message). Outline fail → không gọi draft."""
    if isinstance(day, str):
        day = int(day) if day.strip().lstrip("-").isdigit() else None
    item = plan_item(day=day, keyword=keyword)
    kw = keyword or (item or {}).get("keyword", "")
    if not kw:
        from utils.keywords import load_keywords
        kws = load_keywords()
        kw = kws[0] if kws else ""
    if not kw:
        return None, ("Chưa có từ khóa để sinh bài — thêm `--generate \"từ khóa\"` hoặc "
                      "điền config/keywords.json.")

    focus = (item or {}).get("target", "")
    ctype = (item or {}).get("type", "blog")
    op = cp.outline_prompt(kw, focus, ctype, focus)
    if dry_run:
        preview = cp.draft_prompt("(dàn ý sẽ sinh ở bước 1)", kw, topic=focus, content_type=ctype)
        return None, "[dry-run] Prompt sẽ gửi tới Ollama:\n\n%s\n\n----\n\n%s" % (op, preview)

    client = client or _client()
    outline, err = client.generate(op)
    if err:
        return None, "Không sinh được dàn ý: %s" % err
    draft, err = client.generate(cp.draft_prompt(outline, kw, topic=focus, content_type=ctype))
    if err:
        return None, "Không sinh được bản nháp: %s" % err
    path, _text = render_article(kw, (outline, draft), item, out_dir=out_dir)
    return path, "Đã lưu bản nháp."


def run_generate_cli(keyword="", day=None, dry_run=False):
    """In kết quả, trả mã thoát: 0 ok / 1 Ollama lỗi / 2 thiếu đầu vào. Không sys.exit."""
    if isinstance(day, str):
        if day.strip().lstrip("-").isdigit():
            day = int(day)
        elif day.strip():
            print("[Content] `--day` phải là số nguyên, nhận %r." % day)
            return 2
        else:
            day = None
    path, msg = generate_article(keyword=keyword, day=day, dry_run=dry_run)
    if dry_run:
        print(msg)
        return 0
    if path is None:
        print("[Content] " + msg)
        return 2 if "từ khóa" in msg else 1
    print("[Content] OK " + path)
    text = open(path, encoding="utf-8").read()
    check = cp.seo_check(text, keyword or "")
    print("[Content] Kiểm tra SEO — H1 chứa từ khóa: %s | xuất hiện %s lần | 2 đoạn đầu: %s"
          % ("có" if check["in_h1"] else "không", check["occurrences"],
             "có" if check["first_two_ok"] else "không"))
    return 0
