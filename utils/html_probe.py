"""
utils/html_probe.py — F6: bóc những gì audit on-page cần từ HTML tĩnh.

Dùng `html.parser` stdlib thay vì beautifulsoup4: số thứ cần đọc rất nhỏ (title,
meta description, canonical, heading, ảnh, link, robots, charset, lang) và owner
không muốn thêm dependency cho việc stdlib làm được.

Thuần: không IO, không network, không raise — HTML bị hỏng tới đâu cũng trả về đủ
keys để `site_auditor` còn báo được "trang này đọc không được".
"""
import re
from html.parser import HTMLParser

_HEADING_LEVELS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
# text trong mấy thẻ này không phải nội dung người đọc — không tính vào word_count
_HIDDEN_TEXT_TAGS = {"script", "style", "noscript", "template"}
_CHARSET_RE = re.compile(r"charset\s*=\s*['\"]?([\w-]+)", re.IGNORECASE)


def _ws(text: str) -> str:
    return " ".join((text or "").split())


def _attr(attrs: list, name: str) -> str:
    """Giá trị attribute đầu tiên, '' khi thiếu hoặc attribute trần (`<img alt>`)."""
    for key, value in attrs:
        if key == name:
            return value if value else ""
    return ""


def _has_attr(attrs: list, name: str) -> bool:
    return any(key == name for key, _ in attrs)


class _Probe(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.meta_description = ""
        self.canonical = ""
        self.noindex = False
        self.charset = ""
        self.lang = ""
        self.h1 = []
        self.headings = []
        self.images = []
        self.links = []
        self._parts = []        # stack buffer cho thẻ đang bắt text
        self._tags = []         # tag tương ứng trên stack
        self._link = None
        self._hidden = 0
        self._texts = []
        self._got_title = False

    # ─── text ────────────────────────────────────────────────────────────────
    def handle_data(self, data):
        if self._hidden or not data:
            return
        self._texts.append(data)
        if self._link is not None:
            self._link["parts"].append(data)
        if self._tags:
            self._parts[-1].append(data)

    def _begin_capture(self, tag):
        self._tags.append(tag)
        self._parts.append([])

    def _end_capture(self, tag) -> str:
        if not self._tags or self._tags[-1] != tag:
            return ""
        self._tags.pop()
        return _ws("".join(self._parts.pop()))

    # ─── tags ────────────────────────────────────────────────────────────────
    def handle_starttag(self, tag, attrs):
        if tag in _HIDDEN_TEXT_TAGS:
            self._hidden += 1
            return

        if tag == "title" and not self._got_title:
            self._got_title = True
            self._begin_capture(tag)
        elif tag in _HEADING_LEVELS:
            self._begin_capture(tag)
        elif tag == "a":
            self._link = {"href": _attr(attrs, "href"),
                          "rel": _ws(_attr(attrs, "rel")).lower(),
                          "parts": []}

        elif tag == "img":
            alt = _attr(attrs, "alt") if _has_attr(attrs, "alt") else None
            self.images.append({"src": _attr(attrs, "src"), "alt": alt})

        elif tag == "meta":
            self._meta(attrs)

        elif tag == "link":
            if "canonical" in _ws(_attr(attrs, "rel")).lower().split():
                self.canonical = self.canonical or _attr(attrs, "href")

        elif tag == "html":
            self.lang = self.lang or _attr(attrs, "lang")

    def handle_endtag(self, tag):
        if tag in _HIDDEN_TEXT_TAGS:
            self._hidden = max(0, self._hidden - 1)
            return

        if tag == "title" and self._got_title:
            self.title = self._end_capture("title")
        elif tag in _HEADING_LEVELS:
            text = self._end_capture(tag)
            level = _HEADING_LEVELS[tag]
            self.headings.append((level, text))
            if level == 1:
                self.h1.append(text)
        elif tag == "a" and self._link is not None:
            link = self._link
            self._link = None
            self.links.append({"href": link["href"],
                               "text": _ws("".join(link["parts"])),
                               "rel": link["rel"]})
        elif self._tags and self._tags[-1] == tag:
            self._end_capture(tag)

    # link text cũng phải vào buffer của thẻ cha (h1 trong a, v.v.)
    def _meta(self, attrs):
        name = _attr(attrs, "name").lower()
        equiv = _attr(attrs, "http-equiv").lower()
        content = _attr(attrs, "content")

        if _has_attr(attrs, "charset"):            # <meta charset="UTF-8">
            self.charset = self.charset or _attr(attrs, "charset")
        elif name == "description":
            self.meta_description = self.meta_description or _ws(content)
        elif name in ("robots", "googlebot", "slurp", "bingbot"):
            if "noindex" in _ws(content).lower():
                self.noindex = True
        elif equiv == "content-type" and not self.charset:
            found = _CHARSET_RE.search(content)
            if found:
                self.charset = found.group(1)


def probe(html: str) -> dict:
    """HTML string -> dict dữ liệu cho rules. Không bao giờ raise."""
    parser = _Probe()
    for feed in (lambda: parser.feed(html or ""), parser.close):
        try:
            feed()
        except Exception:
            pass          # HTML hỏng = một finding "không đọc được", không phải crash
    words = " ".join(parser._texts)
    return {
        "title": parser.title,
        "meta_description": parser.meta_description,
        "canonical": parser.canonical,
        "h1": list(parser.h1),
        "headings": list(parser.headings),
        "images": list(parser.images),
        "links": list(parser.links),
        "noindex": parser.noindex,
        "charset": parser.charset,
        "lang": parser.lang,
        "word_count": len(_ws(words).split()),
    }
