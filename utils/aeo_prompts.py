# -*- coding: utf-8 -*-
"""utils/aeo_prompts.py — P2-3: biến thể câu hỏi AEO cho mỗi từ khóa.

Vì sao nhiều câu hỏi: AI engine trả lời khác nhau tùy CÁCH HỎI — chỉ hỏi 1 câu
phẳng là chỉ đo được 1 góc visibility. Bộ góc (angles) gồm:

- best   : "top / tốt nhất"     — câu AEO kinh điển, list thường nhắc brand
- compare: so sánh / đánh giá   — brand xuất hiện khi có kình địch
- how    : cách làm / quy trình — mục đích thông tin, kiểm soát về mắt local
- local  : khu vực gần /\ địa danh — đúng với từ khóa local (quận, tphcm)
- url    : hướng dẫn thẳng có URL site — kiểm tra engine có dẫn link không

Templates dùng {kw} (từ khóa nguyên bản, giữ dấu) và {site} (domain). Dán tay
câu nào vào engine nào cũng được — tool chỉ PHÁT câu, không tự hỏi AI.
"""
import config.settings as cfg
from utils import site_paths

ANGLE_TEMPLATES = {
    "best": "{kw} tốt nhất?",
    "compare": "Đánh giá và so sánh các địa chỉ {kw} — nơi nào nổi bật?",
    "how": "Quy trình {kw} gồm những bước nào? Lưu ý gì?",
    "local": '{kw} gần đây — {site} có nên được nhắc đến không?',
    "url": "Trong các lựa chọn {kw}, có {site} không? Vì sao?",
}

ANGLE_NOTES = {
    "best": "câu kinh điển — phục vụ check list-brand hàng ngày",
    "compare": "nhắc brand khi có kình địch — đo cạnh tranh",
    "how": "mục đích thông tin — máy có dẫn về chuyên môn không",
    "local": "khớp local intent — đo nhắc brand khi hỏi theo vùng",
    "url": "đo engine có dẫn URL site không — khó nhất",
}

ANGLE_ORDER = ("best", "compare", "how", "local", "url")

DEFAULT_ANGLES = ("best", "compare", "local")


def build_questions(keyword: str, angles=None, site: str = "") -> list[tuple[str, str]]:
    """[(angle, câu hoàn chỉnh)] theo thứ tự ANGLE_ORDER. Angle rác (không có
    template) bị bỏ qua. angles=None → dùng DEFAULT_ANGLES; danh sách truyền
    vào (kể cả trống) được tôn trọng — filter xong rỗng là rỗng, không fallback."""
    if angles is None:
        angles = DEFAULT_ANGLES
    angles = [a for a in angles if a in ANGLE_TEMPLATES]
    kw = " ".join(str(keyword or "").split())
    site = (site or site_paths.site_domain() or "").strip()
    out = []
    for a in angles:
        text = ANGLE_TEMPLATES[a].format(kw=kw, site=site)
        out.append((a, text))
    return out


def questions_text(keyword: str, angles=None) -> str:
    """In từng câu + engine gợi ý để copy-paste nhiều engine — không request nào."""
    qs = build_questions(keyword, angles)
    if not qs:
        return ("  Không angle nào hợp lệ — kiểm tra lại tham số "
                f"({', '.join(ANGLE_ORDER)}).")
    site = site_paths.site_domain()
    lines = [f'  CÂU HỎI AEO CHO "{keyword}" — hỏi từng engine, copy câu trả lời:',
             "  " + "-" * 68]
    for angle, q in qs:
        note = ANGLE_NOTES.get(angle, "")
        lines.append(f'  [{angle:<7}] {q}')
        if note:
            lines.append(f'            ({note})')
    lines.append("  " + "-" * 68)
    engines = "ChatGPT / Gemini / Perplexity / Copilot"
    lines.append(f"  Engine dán tay: {engines} | Sau khi hỏi:")
    lines.append('    python main.py --aeo-check answer.txt --aeo-engine ChatGPT '
                 f'--aeo-keyword "{keyword}"')
    if site:
        lines.append(f"  Site đo: {site}")
    return "\n".join(lines)


def run_aeo_questions_cli() -> int:
    """`--aeo-questions "kw" [--aeo-angle best,compare,...]` — in câu hỏi, không gọi mạng."""
    import sys

    def flag_value(name: str) -> str:
        """Giá trị ngay sau cờ — y như _flag_value ở main.py (không import ngược)."""
        if name not in sys.argv:
            return ""
        i = sys.argv.index(name)
        return sys.argv[i + 1] if i + 1 < len(sys.argv) else ""

    kw = flag_value("--aeo-questions") or ""
    if not kw:
        print('[AEO] Thiếu từ khóa — python main.py --aeo-questions "nối mi quận 7"')
        return 2
    angles_raw = flag_value("--aeo-angle") or ""
    angles = [a.strip() for a in angles_raw.split(",") if a.strip()] \
        if angles_raw else None
    print(questions_text(kw, angles=angles))
    return 0
