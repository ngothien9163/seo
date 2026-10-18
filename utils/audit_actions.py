# -*- coding: utf-8 -*-
"""
utils/audit_actions.py — C2: biến findings audit thành việc cần làm theo từ khóa.

Audit (--audit) chỉ nói "trang nào lỗi gì" — owner còn phải tự đoán việc đó
ảnh hưởng từ khóa nào. Module này ghép hai mảnh: URL của finding ↔ từ khóa
(tiếng Việt khong dấu) trong config/keywords.json, rồi sắp xếp theo severity
(CAO trước) và in ra ≤ N việc ưu tiên.

Matching ngưỡng: so TOKEN của URL (bỏ đuôi file/param/stopword web) với token
của từ khóa, cả hai đã fold không dấu bằng _fold duy nhất của repo
(gsc_client._fold). Trang từ khóa phải khớp >= MIN_URL_TOKENS token có
nghĩa — /blog/p5 hay trang chủ rỗng không bao giờ trúng, tránh gán việc
audit trang chủ cho 12 từ khóa khác nhau chỉ vì chúng cùng domain.

Chạy:
    python main.py --audit-actions       # gợi ý việc sau khi đã chạy --audit
    python main.py --audit-actions --limit 5   # nhiều/ít việc hơn

Không gửi request nào — chỉ đọc audit_last.json + keywords.json.
"""
import os
import re
import sys
from urllib.parse import urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# URL phải khớp >= N token "thật" của từ khóa: tránh gán trang con rẻ tiền
MIN_URL_TOKENS = 2
# từ khóa "thấp" severity phải cụ thể hơn (>= 3 token) mới thành việc ưu tiên
MIN_URL_TOKENS_LOW = MIN_URL_TOKENS + 1
# từ khóa trần 2 token (tối thiểu để chia) thì cần >= 2/2 token khớp — chặt tự nhiên

STOPWORDS_URL = {"blog", "tin", "bai", "page", "adm", "category", "danh", "muc",
                 "vi", "vn", "www", "html", "htm", "php", "aspx", "index", "p"}

SEVERITY_ORDER = ("CAO", "TRUNG BÌNH", "THẤP")   # sắp y hệt site_auditor


def _fold(s: str) -> str:
    """Fold không dấu — bản duy nhất của repo nằm ở gsc_client (aeo cũng dùng nó)."""
    from utils.gsc_client import _fold as gsc_fold
    return gsc_fold(s)


def _url_tokens(url: str) -> list[str]:
    """URL → token có nghĩa (path, đã bỏ đuôi file + query/# + stopword web)."""
    try:
        path = urlsplit(str(url)).path or str(url)
    except Exception:
        path = str(url)
    path = re.sub(r"\.(html?|htm|php|aspx)$", "", path, flags=re.IGNORECASE)
    toks = [t for t in re.split(r"[^0-9a-z]+", _fold(path)) if t]
    return [t for t in toks if t not in STOPWORDS_URL and len(t) > 1]


def _kw_tokens(kw: str) -> list[str]:
    """Từ khóa → token có nghĩa, fold không dấu, bỏ stopword web."""
    toks = [t for t in re.split(r"[^0-9a-z]+", _fold(str(kw))) if t]
    return [t for t in toks if t not in STOPWORDS_URL and len(t) > 1]


def match_keyword(url: str, keywords: list[str]) -> str:
    """Từ khóa khớp tốt nhất cho URL, '' khi không có từ khóa nào đủ cụ thể.

    Điểm từ khóa: số token riêng khớp. Cần >= MIN_URL_TOKENS (3 nếu finding
    severity THẤP). Hai từ khoá bằng điểm → từ khóa nhiều token hơn thắng
    (cụ thể hơn); vòng hoà nữa thì từ khóa xuất hiện trước trong keywords.json
    (nhờ sort ổn định của min với tie).
    """
    if not url:
        return ""
    utoks = _url_tokens(url)
    if not utoks:
        return ""
    best, best_score = "", (-1, 0)
    for kw in keywords or []:
        ktoks = _kw_tokens(kw)
        if len(ktoks) < MIN_URL_TOKENS:
            continue              # từ khóa ngắn không đủ chia để khớp 'đủ cụ thể'
        hits = sum(1 for t in ktoks if t in utoks)
        score = (hits, len(ktoks))
        if score > best_score:
            best_score, best = score, kw
    if best_score[0] < MIN_URL_TOKENS:
        return ""
    return best


def build_actions(findings: list, keywords: list, limit: int = 5) -> list[dict]:
    """findings audit (rule/severity/url/detail) + danh sách từ khóa
    → các việc ưu tiên: {keyword, severity, rule, url, detail}.

    Finding không khớp từ khóa nào (trang chủ, URL lạ) vẫn được giữ lại với
    keyword='' — group 'Trang chủ/tổng' ở phần in, vì lỗi trang chủ ảnh hưởng
    mọi từ khóa. Sắp xếp CAO→THẤP rồi giữ nguyên thứ tự findings (audit đã
    xếp theo trang).

    Trả [] khi findings rỗng — chất khác: 'chưa có audit',
    người dùng cần chạy --audit TRƯỚC; build_actions không phải biến chất đó.
    """
    out = []
    for f in findings or []:
        if not isinstance(f, dict):
            continue
        rule = str(f.get("rule") or "").strip()
        severity = str(f.get("severity") or "THẤP").strip()
        url = str(f.get("url") or "").strip()
        detail = str(f.get("detail") or "").strip()
        if not rule or not url:
            continue
        kw = match_keyword(url, keywords or [])
        out.append({"keyword": kw, "severity": severity, "rule": rule,
                    "url": url, "detail": detail})
    rank = {sev: i for i, sev in enumerate(SEVERITY_ORDER)}
    out.sort(key=lambda a: (rank.get(a["severity"], len(rank)),))
    if limit and limit > 0:
        out = out[:limit]
    return out


def actions_text(actions: list, saved_at: str = "") -> str:
    """Actions → phần in cuối cùng (kèm hằng ngưỡng số). Trả các dòng print."""
    lines = []
    lines.append("=" * 70)
    head = "  VIỆC ƯU TIÊN SAU AUDIT (CAO trước — tối đa %d việc)" % 5
    lines.append(head)
    lines.append("=" * 70)
    if saved_at:
        lines.append(f"  Dữ liệu từ audit lúc: {saved_at}")
    if not actions:
        lines.append("  Chưa có findings nào → chạy python main.py --audit trước.")
        lines.append("  (Đoàn trang được đọc: target URL + sitemap.xml trong robots.txt)")
    else:
        for a in actions:
            if a["keyword"]:
                title = f'"{a["keyword"]}"'
            else:
                title = "Trang chủ/tổng"
            lines.append(f'  [{a["severity"]}] {title}: {a["rule"]} — {a["url"]}')
            if a["detail"]:
                lines.append(f'      {a["detail"][:110]}')
    return "\n".join(lines)


def run_audit_actions_cli() -> int:
    """Entry `--audit-actions`: in việc ưu tiên theo từ khóa. Exit 0."""
    from utils.site_auditor import load_last_audit, _state_path
    from utils.keywords import load_keywords

    raw = None
    try:
        with open(_state_path(), encoding="utf-8") as fh:
            import json
            raw = json.load(fh).get("saved_at", "")
    except Exception:
        raw = ""
    findings = load_last_audit()
    keywords = load_keywords()
    # --limit N: y như các flag CLI khác của repo — lấy trang token kế sau, số nguyên
    lim = 5
    if "--limit" in sys.argv:
        i = sys.argv.index("--limit")
        if i + 1 < len(sys.argv):
            try:
                lim = max(int(sys.argv[i + 1]), 1)
            except ValueError:
                pass
    actions = build_actions(findings, keywords, limit=lim)
    if not findings and not raw:
        print(f"Chưa có audit gần nhất ({_state_path()} không tồn tại).")
        print("Chạy python main.py --audit trước, sau đó mới có việc ưu tiên.")
        return 0
    print(actions_text(actions, saved_at=str(raw)))
    if not findings:
        print("File audit có nhưng trống findings — kiểm tra lại lần --audit gần nhất.")
    elif not actions:
        print("Findings không thành hành động nào (thiếu từ khóa khớp?).")
    return 0
