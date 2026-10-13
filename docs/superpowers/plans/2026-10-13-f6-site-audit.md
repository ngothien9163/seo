# F6 — Site audit on-page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development / executing-plans. Bước theo checkbox.

**Goal:** `python main.py --audit` tự crawl site mục tiêu (≤100 trang, chỉ cùng domain), soi các lỗi on-page hay gặp nhất (title / meta description / H1 / thứ tự heading / alt ảnh / canonical / link nội bộ hỏng / http không bảo mật / robots + sitemap), in báo cáo **kèm severity + URL**, xuất CSV bằng đúng mạch của F1, và (`--pagespeed`) lấy Core Web Vitals từ PageSpeed Insights API.

**Architecture:** 3 lớp tách bạch, mỗi lớp test được không cần network:
`utils/html_probe.py` (HTML string → dict dữ liệu, `html.parser` stdlib, **không dependency mới**) →
`utils/site_auditor.py` (rule engine thuần trên dict đó + crawler `requests` có queue/visited/robots/timeout) →
CLI/GUI/CSV. `utils/pagespeed.py` là nhánh riêng: gọi API Google, thất bại thì báo cáo vẫn in đủ.

**Tech Stack:** Python 3.11 stdlib (`html.parser`, `urllib.parse`, `json`, `re`) + `requests` (đã có trong requirements.txt). **Không** Playwright — roadmap card ghi là audit HTML tĩnh.

**Spec:** không có file spec riêng (F6 là card *bounded* theo roadmap line 121: chỉ cần mini-design). Mọi quyết định của card nằm ở mục "Quyết định đã chốt" dưới đây.

## Global Constraints

- **Không thêm dependency.** Card F6 gợi ý `beautifulsoup4`; plan này **từ chối** và dùng `html.parser` stdlib (owner đã nêu rõ: không giải quyết khoảng trống cục bộ bằng cách thêm package). Chỉ cần lấy title/meta/h1/h2…/img/href/canonical/rel — stdlib đủ. Nếu sau này cần selector phức tạp thì tính lại, không lén thêm import.
- **Chỉ chạm domain mục tiêu.** Crawler so `netloc` với `urlsplit(TARGET_URL)` sau khi bỏ `www.` — link ra ngoài domain **không bao giờ** được fetch (kể cả sitemap.xml trỏ sang host khác). Test bằng fake fetcher đếm URL.
- **Tôn trọng robots.txt** của site đích: `Disallow` khớp prefix thì không request, không báo lỗi — chỉ ghi chú "N URL bị robots chặn, không audit". robots.txt lỗi/không có → coi như cho phép hết.
- Timeout mặc định **10 s/req** (card: link hỏng không được treo audit); mỗi URL request **tối đa 1 lần** (`visited`); giới hạn **100 trang/lần** (`AUDIT_MAX_PAGES`, đổi được bằng `--audit-limit N`).
- HTTP 404/500 của một trang **là dữ liệu**, không phải crash: trang 404 → finding `link nội bộ hỏng`; trang 5xx/timeout → finding `Không đọc được trang` severity CAO, crawler đi tiếp.
- Rule **không được gọi network**: `audit_html(url, html) -> list[Finding]` nhận HTML string; crawler chỉ việc gom kết quả.
- `Finding` = dict cố định: `{"rule", "severity", "url", "detail"}`; severity ∈ `("CAO", "TRUNG BÌNH", "THẤP")` — tiếng Việt, in đúng thứ tự ưu tiên rồi mới tới URL.
- CSV tái dùng `utils/exporter.py`: **không** tự `csv.writer` ở module khác; thêm `exporter.export_audit(rows)` gọi `_unique_path("audit")` + `_write_csv` để BOM + tên file nhất quán một chỗ.
- PageSpeed: API `https://www.googleapis.com/pagespeedonline/v5/runPagespeed` **không key** (quota thấp là đủ cho 1 site). Không in response thô (rất lớn) — chỉ LCP/CLS/INP/ điểm + ngày giờ, lưu `data/pagespeed.json`. Không key / hết quota / mất mạng → in lý do tiếng Việt, exit 1, **báo cáo audit HTML vẫn chạy bình thường** (độc lập).
- `data/` (đã gitignore từ F3) là nơi pagespeed.json; mọi path đi qua một hàm duy nhất kiểu `alerts._state_path()` để còn hedge F10.
- Console Windows cp1252: **không** được để in tiếng Việt làm crash (`main.py` đã reconfigure UTF-8 từ F4 — các module mới chỉ cần không tự bắt `SystemExit` tùy tiện).
- Test `_quick_audit_test.py` ở root (gitignored), assert thuần, không pytest, **không network** (monkeypatch fetcher), chạy với `PYTHONIOENCODING=utf-8`.
- Mỗi task một commit.

## Review Focus

1. Parser stdlib có bỏ sót `<img>` tự đóng / attribute không có dấu nháy / `<title>` chứa script không? Test bằng HTML cố tình xấu.
2. Rule "title trùng" phải chỉ báo khi trùng **giữa các trang khác URL**, và không được nổ khi crawler mới đọc 1 trang.
3. Crawler không được lạc sang domain khác (kể cả `//fonts.googleapis.com`, `mailto:`, `tel:`, `javascript:`, `#anchor`) — test bằng trang giả có link ngoài.
4. Relative URL (`/blog/a`, `./a`, `a/`, query `?utm=`) phải chuẩn hóa về absolute + **bỏ query tracking** trước khi cho vào `visited`, nếu không một trang bị tính N lần.
5. `robots.txt` parse thủ công: user-agent `*` vs UA cụ thể, `Disallow: /` khác `Disallow: /wp-admin/`; không được dùng `urllib.robotparser` rồi giả định nó đúng với `Allow`? (dùng `robotparser` là OK — nhưng phải test 2 case trên.)
6. Severity có cơ sở, không phải màu trang trí: thiếu title/meta = CAO (ảnh hưởng CTR trực tiếp), alt thiếu = TRUNG BÌNH, title dài = THẤP.
7. Trang đích trả HTML rỗng/encoding lỗi → một finding, không raise.

## Quyết định đã chốt

| Câu hỏi | Chốt | Lý do |
|---|---|---|
| Parser | `html.parser` stdlib, **không** thêm beautifulsoup4 | Owner: không thêm dependency cho việc stdlib làm được; số attribute cần đọc rất nhỏ. |
| Nguồn URL | `sitemap.xml` trước, fallback crawl theo link nội bộ | Card yêu cầu cả hai; sitemap cho coverage nhanh, crawl cho site không có sitemap. |
| Giới hạn | 100 trang/lần, timeout 10 s | Card "site 50 trang ~2 phút" + "link hỏng không treo audit". |
| Chạy bằng gì | `requests` + UA desktop tĩnh, **không** Playwright | HTML tĩnh WordPress/WooCommerce đủ; tránh đụng lớp anti-detect — lớp đó đã tuyên bố không đụng từ đầu. |
| Core Web Vitals | PSI API không key, mobile + desktop, lưu `data/pagespeed.json` | Miễn phí, không cần hạ tầng; không key thì quota thấp — chấp nhận, xử lý 429 bằng thông điệp. |
| Ngoài phạm vi | audit JS-rendered sâu, so sánh 2 lần audit, đề án sửa lỗi tự động | Theo card. |

---

### Task 1: `utils/html_probe.py` — HTML → dữ liệu (thuần, offline)

**Files:** Create `utils/html_probe.py`, Create `_quick_audit_test.py`.

**Interfaces (Produces):** `probe(html: str) -> dict` với keys: `title` (str, đã normalize whitespace, `""` nếu thiếu), `meta_description`, `canonical`, `h1` (list[str]), `headings` (list[(level:int, text)] theo đúng thứ tự xuất hiện), `images` (list[{"src","alt"}] — alt `None` khi **không có attribute**, `""` khi alt rỗng có chủ ý), `links` (list[{"href","text","rel"}]), `noindex` (bool), `charset`, `lang`, `word_count`. Tất cả là string/None, không raise với HTML hỏng.

- [x] Step 1 — Test fail trước: HTML đủ/ thiếu từng thành phần; `<img src=a>` không nháy; `<IMG ALT="">` hoa; `<title>` chứa tag lồng; heading nhảy cấp `h1→h3`; 2 `<h1>`; `rel="nofollow noopener"` nhiều giá trị; `<meta name="robots" content="noindex, nofollow">`; `NAME=`/`CONTENT=` viết hoa; self-closing `<br/>`; HTML cụt (`"<div><p>x"`) vẫn trả dict; AST cấm import `requests/socket/urllib/http` và cấm gọi `open()`.
- [x] Step 2 — Chạy → FAIL (`ModuleNotFoundError: No module named 'utils.html_probe'`).
- [x] Step 3 — Implement `_Probe(HTMLParser)` với `convert_charrefs=True`: stack buffer cho title/heading, buffer riêng cho text của `<a>` (nên `Đi <b>xem</b>` → "Đi xem"), `_hidden` counter cho script/style/noscript/template, `_attr`/`_has_attr` phân biệt **thiếu alt** (`None`) với **alt rỗng chủ ý** (`""`), charset lấy từ `<meta charset>` lẫn `http-equiv=Content-Type`, `feed`/`close` bọc `try/except` (HTML hỏng = một finding, không phải crash).
- [x] Step 3b — **Test ban đầu sai về HTML, đã sửa test chứ không sửa code:** `<title>A <span>B</span></title>` — `HTMLParser` đối xử với `title` như **RCDATA**, nên `<span>` ở lại nguyên văn (đúng như browser hiểu và đúng như Google sẽ hiển thị). Test cũ đòi "A B" → đổi thành `test_probe_title_is_rcdata_so_nested_tags_stay_literal` + thêm `test_probe_heading_text_joins_nested_tags` cho trường hợp lồng tag **có** thật (`<h1>A <span>B</span> C</h1>` → "A B C"). Audit không tự "dẹp" markup lỗi hộ chủ site.
- [x] Step 4 — Test → **ALL PASS (15)**; **5/5 mutation CAUGHT** (bỏ `_HIDDEN_TEXT_TAGS`, gộp alt thiếu với alt rỗng, nhận mọi `<link>` là canonical, bỏ `<meta charset>`, sort headings theo cấp thay vì theo thứ tự tài liệu); CJK scan `utils/html_probe.py` = 0; `_quick_test`/`_quick_alert_test`/`_quick_scheduler_test` và 3 suite còn lại vẫn PASS (không đổi file dùng chung nào).
- [x] Step 5 — Commit: `feat: F6 html probe (html.parser stdlib, khong them dependency)`

### Task 2: `utils/site_auditor.py` — rules + crawler

**Files:** Modify `config/settings.py` (PHẦN H), Create `utils/site_auditor.py`, Modify `_quick_audit_test.py`.

**Interfaces:** `Finding` dict shape (xem Global Constraints); `RULES: list[callable]`; `audit_html(url, html) -> list[dict]`; `crawl(start_url, max_pages, fetcher=default_fetcher) -> list[Page]` với `Page = {"url","status","html","error"}`; `RobotsPolicy(robots_text)` → `.allowed(url)`; `run_audit_cli(limit=None) -> int`; `audit_rows(findings) -> (header, rows)` cho CSV.

Rules bắt buộc (mỗi rule một hàm nhỏ, test độc lập): thiếu `title` (CAO) · title > 65 hoặc < 30 ký tự (THẤP) · title trùng giữa các trang (TRUNG BÌNH) · thiếu meta description (CAO) · meta > 165 ký tự (THẤP) · không có `h1` (CAO) · nhiều `h1` (TRUNG BÌNH) · heading nhảy cấp (TRUNG BÌNH) · ảnh thiếu `alt` (TRUNG BÌNH, detail ghi số lượng + 3 src đầu) · `alt=""` trên ảnh nội dung lớn thì nhắc (THẤP) · canonical thiếu (THẤP) · canonical trỏ domain khác / http (CAO) · `noindex` trên trang thường (CAO) · link nội bộ 404 (CAO, tính từ link đã fetch) · link `http://` cùng domain (TRUNG BÌNH — redirect thừa) · lang thiếu (THẤP) · sitemap.xml không tìm thấy (THẤP).

- [ ] Step 1 — Test fail trước (crawler với **fake fetcher**, không network): sitemap.xml được ưu tiên và chỉ lấy URL cùng domain; không có sitemap → crawl theo link nội bộ; chuẩn hóa `?utm=`/`#frag`/`./`/`//host/path`; **không bao giờ** fetch ngoài netloc; `visited` chống fetch trùng; quá `max_pages` thì dừng đúng ngưỡng; 404 → finding "link nội bộ hỏng" mà không phá queue; timeout/5xx → finding "Không đọc được trang", crawler đi tiếp; robots Disallow `/` với UA `*` → 0 URL được fetch + ghi chú; `Allow` thắng `Disallow` dài hơn.
- [ ] Step 2 — Chạy → FAIL.
- [ ] Step 3 — Implement rules (từng hàm nhận `Page` + `probe` dict) + `RobotsPolicy` (bọc `urllib.robotparser`, test 2 case ở Review Focus 5) + `crawl()` (requests, timeout, UA tĩnh, header `Accept: text/html`, không theo redirect ra ngoài domain).
- [ ] Step 4 — Test → ALL PASS (rules + crawler) + scan CJK.
- [ ] Step 5 — Commit: `feat: F6 site auditor: 16 rule on-page + crawler chi cham domain muc tieu`

### Task 3: `utils/pagespeed.py` — Core Web Vitals (PSI, không key)

**Files:** Modify `config/settings.py` (PHẦN H tiếp), Create `utils/pagespeed.py`, Modify `_quick_audit_test.py`.

**Interfaces:** `fetch(url, strategy) -> dict|None` (posts-free GET, timeout 60 s — PSI chậm hơn 10 s nhiều, ghi rõ trong docstring), `run_pagespeed_cli(url=None) -> int`, `load_saved()` / `data/pagespeed.json` shape `{"url","fetched_at","mobile":{...},"desktop":{...}}` — **không** lưu cả response (vài MB).

- [ ] Step 1 — Test fail trước (mock `requests`): parse `lighthouseResult.audits["largest-contentful-paint"].displayValue` + `cumulative-layout-shift` + `interaction-to-next-paint` + `performance-score` → dict gọn; HTTP 429 → thông điệp "hết quota, thử lại sau" + exit 1, **không** raise; thiếu mạng (`ConnectionError`) → thông điệp + exit 1; JSON không có `lighthouseResult` (PSI đang chạy) → thông điệp rõ; response lớn không được in ra console; file lưu lại đọc được bằng `load_saved()`.
- [ ] Step 2 — Chạy → FAIL.
- [ ] Step 3 — Implement.
- [ ] Step 4 — **Verify thật**: `python main.py --pagespeed` trên máy có mạng → in điểm mobile+desktop hoặc thông điệp quota rõ ràng; xác nhận `data/pagespeed.json` không chứa response thô và **không** chứa token (API không key → không có secret, vẫn assert không in URL query dài).
- [ ] Step 5 — Commit: `feat: F6 pagespeed insights (PSI khong key, luu diem CWV vao data)`

### Task 4: CLI `--audit` + CSV + GUI + README

**Files:** Modify `main.py`, `utils/exporter.py`, `ui.py`, `README.md`, Modify `_quick_audit_test.py`.

- [ ] Step 1 — Test fail trước: `main.py` chứa `"--audit"` + `"--pagespeed"` và help in 2 dòng; `exporter.export_audit(rows)` trả `(path, n)` dùng `_unique_path`+`_write_csv` (assert bằng AST rằng `site_auditor.py` **không** import `csv`); README có các needle `--audit`, `--pagespeed`, `AUDIT_MAX_PAGES`, `Audit on-page`, `pagespeed.json`; `ui.py` có `run_site_audit` + widget `btn_audit`.
- [ ] Step 2 — Chạy → FAIL.
- [ ] Step 3 — Implement: `run_audit_cli(limit=None)` in bảng theo nhóm severity (đếm trước, in CAO hết rồi tới TRUNG BÌNH/THẤP), kết luận `N trang / M lỗi (CAO x)`, gợi ý `--export audit`; `--audit-limit 30` parse số, sai → exit 2 + giải thích; CSV header `severity,rule,url,detail`.
- [ ] Step 4 — GUI: nút **🔍  AUDIT SITE** trong hàng nút tab 📈 Xếp Hạng, chạy thread nền `print` vào khung log (stdout đã redirect), disable khi `is_running`; không thêm panel riêng (audit là việc chạy xong rồi xem file).
- [ ] Step 5 — README: mục **"### 12. Audit on-page + Core Web Vitals"**, 2 dòng CLI, bảng PHẦN H, cây project thêm `utils/html_probe.py`/`site_auditor.py`/`pagespeed.py`.
- [ ] Step 6 — **Verify thật**: `python main.py --audit --audit-limit 3` trên site mục tiêu thật (nankybeauty.com — HTML tĩnh, robots công khai) → exit 0, in findings thật, CSV nằm trong `reports/`; mở `data/pagespeed.json` bằng `load_saved()`. Nếu máy không có mạng → ghi rõ "chưa verify online" thay vì đoán.
- [ ] Step 7 — GUI probe: `TrafficBotUI()`, `btn_audit.invoke()`, xác nhận không raise + log in ra (probe đọc `txt_log`).
- [ ] Step 8 — Commit: `feat: F6 cli --audit + xuat CSV qua exporter + nut GUI audit`

## Tiêu chí hoàn thành (card F6)

- Không có sitemap → vẫn audit được bằng crawl.
- Link hỏng không làm treo (timeout 10 s/link), một trang nổ không dừng cả đợt.
- **Không bao giờ** request ra ngoài domain mục tiêu (test đếm URL, không phải tin tưởng).
- Site ~50 trang xong trong cỡ 2 phút (chưa đo được thì ghi số đo thật vào plan, không hứa).
- Kết quả đọc được trên console và mở được bằng Excel (CSV BOM từ exporter).

## Known limitations (ghi nhận, không sửa trong plan này)

- HTML tĩnh: nội dung render bằng JS không được soi (theo card — ngoài phạm vi).
- PSI không key có quota thấp và điểm có thể khác lần đo trước; đây là điểm LAB, không phải CrUX field data — báo cáo phải ghi rõ chữ "LAB".
- Kiểm tra "link nội bộ hỏng" chỉ phát hiện link mà crawler thật sự fetch (≤ max_pages trang); link ngoài domain không được ping (có chủ đích, xem Global Constraints).
- `--audit` request site của chính mình nên không rủi ro pháp lý; nhưng nó **không** phải Googlebot — thứ hạng thật có thể khác những gì HTML tĩnh thể hiện.
