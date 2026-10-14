"""content_prompts — F8: builder prompt + kiểm tra SEO thô, hoàn toàn thuần.

Module này KHÔNG chạm network, KHÔNG import requests/os/subprocess ở đầu file —
mọi hàm là hàm thuần (input → output) nên test được không cần Ollama chạy.
Pipeline thật (gọi Ollama, ghi file) nằm ở utils/ollama_client.py + content/generator.py.
"""
import re
import unicodedata


def _fold(s: str) -> str:
    """Hạ dấu tiếng Việt để so khớp không phân biệt dấu: đ/Đ→d/D (NFD không tách được
    nên phải map tay), NFD + bỏ ký tự combining (Mn), lowercase, gộp khoảng trắng.
    Khớp cả kiểu gõ 'Noi Mi' không dấu."""
    s = (s or "").replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return " ".join(s.lower().split())


def slugify(title: str) -> str:
    """'Nối Mi Tự Nhiên Là Gì?' → 'noi-mi-tu-nhien-la-gi'. Toàn ký tự rác → 'bai-viet'."""
    slug = re.sub(r"[^a-z0-9]+", "-", _fold(title)).strip("-")
    return slug or "bai-viet"


def outline_prompt(keyword: str, focus: str = "", content_type: str = "",
                   angle: str = "") -> str:
    """Yêu cầu Ollama trả DÀN Ý cho một bài tiếng Việt. Không nhắc chuyện đăng bài —
    F8 chỉ sinh nội dung, người dùng tự duyệt và tự đăng."""
    parts = [
        "Bạn là chuyên gia SEO content tiếng Việt. Hãy lập DÀN Ý (outline) chi tiết "
        "cho một bài viết chuẩn SEO, bằng tiếng Việt.",
        f"- Từ khóa chính: {keyword}",
    ]
    if focus:
        parts.append(f"- Góc độ / từ khóa phụ: {focus}")
    if content_type:
        parts.append(f"- Loại content: {content_type}")
    if angle:
        parts.append(f"- Hướng tiếp cận: {angle}")
    parts += [
        "Dàn ý cần có: tiêu đề H1, 3-6 mục H2 kèm 2-3 gạch đầu dòng mỗi mục, "
        "và gợi ý kết bài. Chỉ trả về dàn ý, không viết cả bài.",
    ]
    return "\n".join(parts)


def draft_prompt(outline: str, keyword: str, topic: str = "",
                 content_type: str = "", notes: str = "") -> str:
    """Yêu cầu Ollama viết BÀI ĐẦY ĐỦ từ dàn ý đã sinh ở bước trước."""
    parts = [
        "Dựa vào dàn ý dưới đây, hãy viết một bài viết SEO hoàn chỉnh bằng tiếng Việt "
        f"cho từ khóa '{keyword}'.",
        "Quy tắc: mở đầu nêu vấn đề và nhắc từ khóa sớm; mỗi H2 có nội dung cụ thể, "
        "câu ngắn, dễ đọc; dùng markdown (# cho H1, ## cho H2); dài khoảng 800-1200 từ; "
        "kết bài có lời kêu gọi hành động tự nhiên.",
        "Chỉ trả về markdown của bài viết, không kèm lời dẫn ngoài bài.",
    ]
    if topic:
        parts.append(f"- Chủ đề: {topic}")
    if content_type:
        parts.append(f"- Loại content: {content_type}")
    if notes:
        parts.append(f"- Ghi chú thêm: {notes}")
    parts += ["", "DÀN Ý:", outline]
    return "\n".join(parts)


def build_frontmatter(meta: dict) -> str:
    """Markdown frontmatter '---' bọc các cặp key: value. Giá trị luôn bọc nháy kép
    để một dấu ':' trong value không phá YAML. Trả về đúng một cặp '---'."""
    lines = ["---"]
    for key, value in meta.items():
        lines.append(f'{key}: "{value}"')
    lines.append("---")
    return "\n".join(lines)


def extract_h1(markdown: str) -> str:
    """H1 (dòng '# ') đầu tiên ngoài code fence. Frontmatter và comment trong ``` bị bỏ.
    Không có H1 → ''."""
    in_fence = False
    for line in (markdown or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if stripped.startswith("# ") and not stripped.startswith("##"):
            return stripped[2:].strip()
    return ""


def _body_blocks(markdown: str) -> list:
    """Bỏ frontmatter và dòng H1, chia thành các block cách nhau bởi dòng trống."""
    text = markdown or ""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            nl = text.find("\n", end + 1)
            text = text[nl + 1:] if nl != -1 else ""
    lines = []
    for line in text.splitlines():
        if line.strip().startswith("# ") and not line.strip().startswith("##"):
            continue
        lines.append(line)
    return [b.strip() for b in "\n".join(lines).split("\n\n") if b.strip()]


def seo_check(markdown: str, keyword: str) -> dict:
    """Kiểm tra SEO thô, không raise với nội dung bất kỳ. Fold dấu nên 'Noi Mi' vẫn khớp.

    - in_h1: từ khóa (fold) xuất hiện trong H1 (fold)?
    - occurrences: số lần từ khóa (fold) xuất hiện trong toàn bài.
    - first_two_ok: từ khóa (fold) nằm trong 2 block mở đầu (sau H1)?
    """
    kw = _fold(keyword)
    full = _fold(markdown)
    h1 = _fold(extract_h1(markdown))
    in_h1 = bool(kw) and kw in h1
    occurrences = full.count(kw) if kw else 0
    blocks = _body_blocks(markdown)
    opening = _fold("\n".join(blocks[:2]))
    first_two_ok = bool(kw) and kw in opening
    return {
        "keyword": keyword,
        "in_h1": in_h1,
        "occurrences": occurrences,
        "first_two_ok": first_two_ok,
    }


def assemble(frontmatter: str, body: str) -> str:
    """Glue frontmatter và thân bài thành một tài liệu markdown hoàn chỉnh."""
    return f"{frontmatter.rstrip()}\n\n{body.strip()}\n"
