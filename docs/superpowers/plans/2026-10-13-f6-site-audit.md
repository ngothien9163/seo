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

- [x] Step 1 — Test fail trước (crawler với **fake fetcher**, không network): sitemap.xml được ưu tiên và chỉ lấy URL cùng domain; không có sitemap → crawl theo link nội bộ; chuẩn hóa `?utm=`/`#frag`/`./`/`//host/path`; **không bao giờ** fetch ngoài netloc; `visited` chống fetch trùng; quá `max_pages` thì dừng đúng ngưỡng; 404 → finding "link nội bộ hỏng" mà không phá queue; timeout/5xx → finding "Không đọc được trang", crawler đi tiếp; robots Disallow `/` với UA `*` → 0 URL được fetch + ghi chú; `Allow` thắng `Disallow` dài hơn. **→ Đủ 40 test Task 2, chạy RED trước (`ModuleNotFoundError: No module named 'utils.site_auditor'`), mỗi ý ở trên có ít nhất một test; thêm case ngoài danh sách: redirect ra ngoài domain không được parse link, `alt=""` chỉ nhắc trên trang nội dung dài, trang 404 không nổ rule on-page.**
- [x] Step 2 — Chạy → FAIL như trên; 15 test Task 1 vẫn PASS.
- [x] Step 3 — Implement rules (từng hàm nhận `Page` + `probe` dict) + `RobotsPolicy` + `crawl()` (requests, timeout, UA tĩnh, header `Accept: text/html`, không theo redirect ra ngoài domain).
  - **Deviation 1 — `RobotsPolicy` KHÔNG bọc `urllib.robotparser`.** Review Focus 5 đúng là một cái bẫy: đo trên venv 3.11.15, với `User-agent: *` + `Disallow: /wp-admin/` + `Allow: /wp-admin/adm-adm-post-1.php` thì `can_fetch()` trả **False** — CPython khớp theo **thứ tự khai báo**, còn quy tắc robots của Google là **đường dẫn khớp dài nhất thắng** (bằng độ dài thì dòng khai báo trước thắng). `RobotsPolicy` tự parse theo đúng quy tắc đó; `Disallow:` rỗng = cho phép hết; group UA cụ thể thắng group `*` khi UA khớp prefix; chịu CRLF, comment `#`, `DISALLOW:` viết hoa. `robotparser` chỉ sai ở 1 trong 2 case của Review Focus 5 → bỏ hẳn, không "dùng rồi vá".
  - **Deviation 2 — `crawl()` trả `{"pages": [...], "meta": {...}}`, không phải `list[Page]`** như interface ghi ở đầu task. Ba rule ("thiếu sitemap.xml", "robots.txt chặn", ghi chú trên console) cần tri thức về cả đợt crawl: đã xin sitemap chưa, robots có tồn tại không, bao nhiêu URL bị chặn, queue còn dang dở hay không. `meta` do `_meta(start_url)` khởi tạo nên test dựng thủ công được.
  - **Deviation 3 — số rule thực tế là 20** (14 rule từng trang + 6 rule so giữa các trang), không phải "16" trong card. Danh sách 16 của card thật ra chứa 17 tên, và Global Constraints đòi thêm 3 finding: `không đọc được trang` (5xx/timeout/redirect ngoài domain), `robots.txt chặn`, `trang chết (404/410)` (sitemap còn giữ mà không link nội bộ nào trỏ tới). `RULE_COUNT` do test chốt (`test_rule_names_are_unique_and_rulecount_is_documented`) để con số không tự trôi.
  - **Deviation 4 — `run_audit_cli` về Task 2** (plan Task 4 cũng ghi nó) và nhận thêm `fetcher=` / `url=` để test offline trọn vẹn; Task 4 chỉ nối vào `main.py` + CSV + GUI.
  - Hành vi phụ đã cài và đã test: trang 404 **không** nổ rule on-page (nội dung 404 không phải thứ Google index) và chỉ bị báo bằng **một** rule — `link nội bộ hỏng` gắn vào TRANG CHỨA link, `trang chết` chỉ khi không có link nào trỏ tới; redirect nội bộ ghi `redirected_to` và không fetch lại.
- [x] Step 4 — Test → **ALL PASS (66)**; CJK scan `utils/site_auditor.py` + `config/settings.py` + `_quick_audit_test.py` = 0 hit; chạy lại **cả 7 suite** vì `config/settings.py` là file dùng chung: LOGIC PASS, `[GSC-TEST]`, `[EXPORT-TEST]`, `[KEYWORD-TEST]`, `[ALERT-TEST] 59`, `[SCHED-TEST] 40` — không regression.
  - **Reside đã bắt tại chỗ:** lượt sửa `config/settings.py` đầu tiên tạo block PHẦN H *thứ hai* chồng lên block đã ghi trước đó (Edit chạy hai lần trên cùng một anchor `SCHEDULER_LOCK_STALE`), tức `AUDIT_MAX_PAGES`/`AUDIT_TIMEOUT`/`AUDIT_USER_AGENT` bị khai báo trùng và UA bản sau đè bản trước. `git diff` (18/0 thay vì 9/0) là chỗ lộ ra. Đã xoá block trùng và thêm guard chống lặp vào `test_settings_document_phan_h_for_crawl_limits`: `src.count("PHẦN H:") == 1` + mỗi key đúng một lần khai báo.
  - Mutation trên `utils/site_auditor.py` (driver `_mut_audit.py`, 18 con, đã xoá sau khi chạy): **18/18 CAUGHT**. Vòng đầu có **1 SURVIVED** = "bỏ kiểm tra `visited` phía pop", vì test cycle của tôi chỉ dựng vòng tự tham (A→A) mà không dựng **hình thoi** (A→S và B→S cùng vào queue trước khi S được pop) — đoạn code chống fetch trùng vì thế không bị test nào giữ. Thêm `test_crawl_fetches_shared_target_once_when_two_pages_link_it` → mutant chuyển CAUGHT. Lặp lại bài học cũ: mutant sống thường là **lỗ hổng test**, không phải code thừa.
  - Mutation khác đã soi và kết quả: bỏ `same_host` ở vòng link (2 FAIL), nhận URL ngoài domain từ sitemap, `max_pages` off-by-one (2 FAIL), giữ `?utm=`/giữ fragment, không seed trang chủ (14 FAIL), cho redirect ngoài domain lọt qua, parse link từ trang lỗi, gộp alt thiếu với alt rỗng, bỏ ngưỡng nội dung cho `alt=""`, bỏ kiểm tra host của canonical, báo `thiếu sitemap.xml` khi robots chặn hết, nổ rule on-page trên trang 404 (2 FAIL), trang chết bị báo 2 rule (2 FAIL), `RobotsPolicy` văn bản rỗng = chặn hết (16 FAIL), `Allow` dài hơn thua `Disallow` (khớp theo dòng đầu).
- [x] Step 5 — Commit: `feat: F6 site auditor: 20 rule on-page + crawler chi cham domain muc tieu` — sửa "16" → "20" theo Deviation 3, vì message phải khớp số rule thật trong `RULE_COUNT`.

**Task 2b — addendum (bug crawler do verify thật ở Task 4 bắt được, 2026-10-14).** `crawl()` coi **mọi** `<loc>` trong `/sitemap.xml` là một trang. Với site WordPress/Yoast (nankybeauty.com là một ca thật), `/sitemap.xml` là `<sitemapindex>`: các `<loc>` bên nó là **sitemap con (XML)**, không phải trang → crawler lấy rule on-page áp lên file XML và báo 3 lỗi **CAO giả** ("thiếu title", "thiếu meta description", "thiếu H1" cho `sitemap-0.xml`). Unit test không bắt được vì fixture `<urlset>` của Task 2 đúng là urlset. Đã sửa trong `utils/site_auditor.py`:
- `_sitemap_seeds()`: nhận diện `<sitemapindex>` rồi mới đọc từng sitemap con (tối đa `SITEMAP_INDEX_MAX = 10` file, không đệ quy thêm cấp), gom `<loc>` từ đó; **bộ lọc `.xml` nằm ở MỘT chỗ duy nhất** áp cho cả hai nhánh (mutant "chỉ lọc ở một nhánh" từng sống nên giờ gộp lại).
- `meta["sitemap_files"]` + `visited` khởi tạo bằng robots.txt và các file sitemap đã đọc → bất biến "mỗi URL request tối đa **1** lần" còn đúng khi một trang có link trỏ về `/sitemap.xml` (trước đó: fetch lần hai **và** audit XML lần hai).
- `_meta()` thêm `sitemap_submaps`/`sitemap_truncated`/`sitemap_files`; `_sitemap_note()` in "1 sitemap con → 403 URL cùng domain (chỉ đọc 10 file sitemap con đầu)" khi bị cắt.
- Sau sửa, verify thật: hết finding giả, `CAO 0`, 20 trang/16.25 s.
- Test mới (4): `test_crawl_expands_sitemap_index_but_never_audits_the_xml_as_a_page`, `test_crawl_caps_how_many_sub_sitemaps_are_read`, `test_urlset_listing_a_sitemap_file_does_not_make_it_a_page`, `test_sitemap_files_already_read_are_not_audited_when_a_page_links_to_them`. Mutation: 4 mutant sitemap (không đọc sitemap con / coi `<sitemapindex>` như `<urlset>` / bỏ bộ lọc `.xml` / bỏ `visited` khởi tạo bằng file đã đọc) — **4/4 CAUGHT**.


### Task 3: `utils/pagespeed.py` — Core Web Vitals (PSI, không key)

**Files:** Modify `config/settings.py` (PHẦN H tiếp), Create `utils/pagespeed.py`, Modify `_quick_audit_test.py`.

**Interfaces:** `fetch(url, strategy) -> dict|None` (posts-free GET, timeout 60 s — PSI chậm hơn 10 s nhiều, ghi rõ trong docstring), `run_pagespeed_cli(url=None) -> int`, `load_saved()` / `data/pagespeed.json` shape `{"url","fetched_at","mobile":{...},"desktop":{...}}` — **không** lưu cả response (vài MB).

- [x] Step 1 — Test fail trước (mock `requests`): parse `lighthouseResult.audits["largest-contentful-paint"].displayValue` + `cumulative-layout-shift` + `interaction-to-next-paint` + `performance-score` → dict gọn; HTTP 429 → thông điệp "hết quota, thử lại sau" + exit 1, **không** raise; thiếu mạng (`ConnectionError`) → thông điệp + exit 1; JSON không có `lighthouseResult` (PSI đang chạy) → thông điệp rõ; response lớn không được in ra console; file lưu lại đọc được bằng `load_saved()`. **→ 21 test; ngoài danh sách của plan còn thêm: điểm fallback từ audit `performance-score` khi `categories` vắng mặt, metric thiếu → `''` chứ không crash, message của Google bị cắt dưới 400 ký tự, `load_saved` từ chối file JSON không có `url`, trần timeout khi `PAGESPEED_TIMEOUT` là số âm/chuỗi, và `key` chỉ có trong query khi owner tự điền (log không bao giờ chứa key).**
- [x] Step 2 — Chạy → FAIL (`ModuleNotFoundError: No module named 'utils.pagespeed'`), 66 test Task 1–2 vẫn PASS.
- [x] Step 3 — Implement.
  - **Deviation 1 — `fetch()` luôn trả dict (có key `error`), không trả `None`** như interface ghi. CLI cần in *lý do* (429 / mất mạng / PSI không trả Lighthouse) nên phân biệt "không có gì" và "có gì đó nhưng hỏng" bằng `error`, một đường duy nhất cho cả console lẫn exit code.
  - **Deviation 2 — seam network là `_api_get(url, params, timeout) -> (status, payload, label)`**, `parse()` tách ra thành hàm thuần để test không cần đụng `requests`. Test thay `_api_get` bằng monkeypatch module attribute (`patched(ps, _api_get=...)`), không patch `requests` — ít bề mặt giả hơn.
  - **Deviation 3 — thêm `PAGESPEED_API_KEY = ""` vào PHẦN H** (card chỉ ghi "không key). Lý do bằng số đo thật, xem Step 4: quota ẩn danh của PSI là **`Queries per day` dùng chung toàn cầu**, hết là hết với mọi người, không phải do site hay do máy này. Để trống vẫn chạy y như card; có key thì thoát cảnh đó. Key là secret của owner — code chỉ ghép vào `params`, **không** bao giờ in ra log (test `test_pagespeed_uses_api_key_only_when_owner_sets_one` chốt cả hai chiều: rỗng → không có `key` trong query; có → không xuất hiện trong output).
  - `build_params()` tách riêng cũng vì lý do đó: một chỗ duy nhất quyết định query có gì, test đếm được.
- [x] Step 4 — Test → **ALL PASS (87)**; CJK scan `utils/pagespeed.py` + `config/settings.py` = 0; chạy lại **cả 7 suite** vì `config/settings.py` đổi: LOGIC / GSC / EXPORT / KEYWORD / ALERT(59) / SCHED(40) — không regression.
  - Mutation `utils/pagespeed.py` (driver `_mut_audit3.py`, 18 con, đã xoá sau khi chạy): **18/18 CAUGHT**, restore OK. Hai mutant sống ở vòng đầu và cả hai là **thiếu test chứ không phải code thừa**: (a) `load_saved` chấp mọi dict kể cả không có `url` → thêm `test_pagespeed_load_saved_rejects_a_file_without_url`; (b) hạ `max(30, ...)` xuống `max(1, ...)` không ai phát hiện, vì `cfg.PAGESPEED_TIMEOUT=90` luôn thắng phép `max` → thêm `test_pagespeed_timeout_floor_survives_bad_config` (số âm và chuỗi lỗi).
  - **Verify thật (2026-10-14, có mạng): chạy `--pagespeed` hai lần trên nankybeauty.com → cả mobile lẫn desktop đều 429**, exit 1, không traceback, không file `data/pagespeed.json`, không response thô. Google trả: `Quota exceeded for quota metric 'Queries' and limit 'Queries per day' of service 'pagespeedonline.googleapis.com' for consumer 'project_number:583797351490'` — tức quota ẩn danh **đã cạn ở phía Google**, không phải phía máy này; lần chạy sau đó mới thêm hint `PAGESPEED_API_KEY`.
  - **Chưa verify online:** nhánh THÀNH CÔNG (đọc LCP/CLS/INP/điểm từ `lighthouseResult`) mới chỉ chạy với payload Lighthouse giả lập, vì 429 chắn trước. Không được nói là "đã đo thật Core Web Vitals" cho tới khi có key hoặc quota hồi.
- [x] Step 5 — Commit: `feat: F6 pagespeed insights (PSI khong key, luu diem CWV vao data)` — vẫn đúng (mặc định không key), key chỉ là lối tùy chọn.


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

**Đã làm (2026-10-14) — tick + deviation thay cho checklist trên:**

- [x] Step 1 — 15 test mới, RED thật 11 FAIL. Banned: import `main.py` (sợ chạm mạch traffic) → đo flags/help/hàm gọi bằng **AST** (`_strings_in`, `_called_names`, tìm `Call` có keyword `limit`); `site_auditor.py` **không import `csv`** cũng bằng AST; README needle đọc **đúng nhánh `utils/` của cây project** (prose nhắc tên file không được tính); state path phải nằm trong `data/` (thư mục đã gitignore từ F3) — kết quả audit chứa URL + lỗi nội bộ, lạc sang `reports/` là nguy cơ commit nhầm.
- [x] Step 2 — **11 FAIL** (RED). Một lỗi do chính test viết sai (`patched()` gọi positional thay vì keyword) — sửa test, không sửa code.
- [x] Step 3 — Implement. **4 deviation:**
  - `exporter.export_audit()` **không nhận `rows`** (plan ghi `export_audit(rows)`). Module F1 đã có hợp đồng "mỗi `export_X()` tự đọc state, trả `(path, n)`"; giữ hợp đồng đó thì `--export audit` chạy được **sau khi** process audit đã thoát (GUI bấm nút hôm qua, hôm nay xuất vẫn còn), và không phải truyền finding qua lại giữa hai module. Nguồn: `data/audit_last.json` do `site_auditor.save_last_audit()` ghi mỗi lần `--audit` đọc được ≥1 trang — chỉ 4 key của finding + `url` + `pages` + `saved_at`, **không chứa HTML**; `load_last_audit()` loại dòng rác/severity lạ và **không raise** khi file thiếu hoặc hỏng JSON.
  - Mapping finding → dòng CSV vẫn **một chỗ** (`site_auditor.audit_rows`); exporter chỉ `load_last_audit()` + `_unique_path("audit")` + `_write_csv`.
  - `--export all` **không** kèm audit: rank/gsc là dữ liệu định kỳ, audit phải tự crawl trước; đổi lại `--audit` kết thúc bằng dòng gợi ý `python main.py --export audit`.
  - `main.py` nhận `--audit-limit` **kể cả khi thiếu `--audit`** (gõ sót thì vẫn audit, không in help rồi bỏ); token kế tiếp bắt đầu bằng `-` → coi như không truyền limit (dùng `AUDIT_MAX_PAGES`), giá trị sai ("abc", số âm) → `run_audit_cli` exit 2 + giải thích.
- [x] Step 4 — GUI: nút **🔍 AUDIT SITE** cuối hàng nút tab 📈 Xếp Hạng; guard `is_running` in lý do (không âm thầm), cờ `_audit_running`, thread nền, `print` của thread xuống khung log; chạy xong **tự gọi `export_audit()`** để "chạy xong rồi xem file" đúng với người chỉ dùng GUI.
- [x] Step 5 — README: mục **"### 12. Audit on-page + Core Web Vitals"**, 3 dòng CLI (`--audit [--audit-limit N]`, `--pagespeed [URL]`, `--export audit`), **7 hàng bảng PHẦN H** (`AUDIT_MAX_PAGES`/`AUDIT_TIMEOUT`/`AUDIT_USER_AGENT`/`AUDIT_STATE_DIR` + `PAGESPEED_*`), cây project thêm `html_probe.py`/`site_auditor.py`/`pagespeed.py`, 2 dòng xử lý sự cố (403/429 và quota PSI), mục "Giới hạn phụ thuộc" ghi rõ **không thêm dependency** (html.parser stdlib thay beautifulsoup4).
- [x] Step 6 — **Verify thật trên nankybeauty.com (có mạng)**:
  - `--audit --audit-limit 3` → exit 0, **3.95 s**; `--audit-limit 20` → exit 0, **16.25 s ≈ 0.8 s/trang** ⇒ 50 trang ~40 s, 100 trang ~80 s. **Số đo thật, thay cho con số "2 phút" trong card.**
  - Findings thật (không phải fixture): `heading nhảy cấp` h2→h4 trên 4/4 trang đầu, `title 107–123 ký tự`, `meta 170–214 ký tự`; đợt 20 trang = **42 lỗi, CAO 0, TRUNG BÌNH 18, THẤP 24**.
  - `--export audit` → `reports/export_20261014_161913_audit.csv`: 42 dòng, BOM `ef bb bf`, header `severity,rule,url,detail`, tiếng Việt không dấu lỗi khi đọc bằng `utf-8-sig`.
  - **Bug thật mà verify bắt được** → xem addendum **Task 2b** bên dưới (sitemap index bị audit như trang).
  - `data/pagespeed.json`: **không tồn tại** — PSI vẫn 429 hết quota ẩn danh (Task 3), nên `load_saved()` chưa có gì để đọc; không fake file này để cho đẹp bước verify.
- [x] Step 7 — GUI probe `_quick_gui_probe_audit.py` (gitignored) dùng **mainloop thật** + stub network: `btn_audit.invoke()` → `run_audit_cli` 1 lần, `export_audit` 1 lần, nút `normal → disabled → normal`, `_audit_running` nhả cờ, 2 dòng `[Audit]` xuất hiện trong `txt_log`, không Traceback → **[GUI-PROBE] OK**. Bài học: bơm `update()` thủ công thay vì `mainloop()` khiến `after()` của thread rơi xuống stderr → probe báo FAIL giả 2 lần; phải đo trong mainloop thật.
- [x] Step 8 — Mutation battery **13/13 CAUGHT** (restore byte-exact có assert; `_mut_audit4.py` đã xóa sau khi chạy). Survivor vòng đầu: `run_audit_cli` bỏ `save_last_audit()` không bị bắt — test đọc leftover của test chạy trước → thêm `cleanup_audit_state()` + đòi file thật sự tồn tại. Trạng thái cuối: **104 audit test PASS**, 7/7 suite PASS, CJK 0 trên mọi file chạm.
- [x] Step 9 — Commit: `feat: F6 cli --audit + xuat CSV qua exporter + nut GUI audit`

## Tiêu chí hoàn thành (card F6)

- Không có sitemap → vẫn audit được bằng crawl. *(test: `test_crawl_without_sitemap_follows_internal_links_only`)*
- Link hỏng không làm treo (timeout 10 s/link), một trang nổ không dừng cả đợt. *(test: 404/timeout → finding, queue đi tiếp; verify thật: 403/429 chỉ là một dòng)*
- **Không bao giờ** request ra ngoài domain mục tiêu (test đếm URL, không phải tin tưởng). *(test: `net.calls` — gồm cả trường hợp sitemap index trỏ sitemap con ở host khác)*
- Site ~50 trang xong trong cỡ 2 phút → **ĐO THẬT 2026-10-14: 20 trang/16.25 s trên nankybeauty.com (≈0.8 s/trang) ⇒ 50 trang ~40 s, nhanh hơn ngưỡng card.**
- Kết quả đọc được trên console và mở được bằng Excel → **VERIFY THẬT: `--audit` in theo nhóm severity (42 lỗi/CAO 0), `--export audit` → `reports/export_20261014_161913_audit.csv` 42 dòng, BOM `ef bb bf`, đọc lại bằng `csv` với `utf-8-sig` nguyên dấu tiếng Việt.**

## Known limitations (ghi nhận, không sửa trong plan này)

- HTML tĩnh: nội dung render bằng JS không được soi (theo card — ngoài phạm vi).
- PSI không key có quota thấp và điểm có thể khác lần đo trước; đây là điểm LAB, không phải CrUX field data — báo cáo phải ghi rõ chữ "LAB".
- **Đo thật 2026-10-14:** quota của PSI không key là `Queries per day` **dùng chung toàn cầu** (không phải của riêng mình), và lúc đo thì **đã cạn** — mọi request đều nhận 429. `--pagespeed` vì vậy hiện in thông báo hết quota + exit 1, nhánh thành công mới chỉ được verify bằng unit test. Lối thoát duy nhất là `PAGESPEED_API_KEY` (tạo miễn phí) — đó là secret của owner, code không bao giờ in ra console/log và không lưu vào `data/pagespeed.json`.
- Kiểm tra "link nội bộ hỏng" chỉ phát hiện link mà crawler thật sự fetch (≤ max_pages trang); link ngoài domain không được ping (có chủ đích, xem Global Constraints).
- `--audit` request site của chính mình nên không rủi ro pháp lý; nhưng nó **không** phải Googlebot — thứ hạng thật có thể khác những gì HTML tĩnh thể hiện.
- `RobotsPolicy` chỉ khớp **prefix** theo quy tắc Google cơ bản; chưa hỗ trợ wildcard `*` và `$` (end-of-url) trong `Disallow`/`Allow`, chưa đọc `Crawl-delay`/`Host:`. Với site WordPress thường gặp thì đủ; nếu gặp robots dùng wildcard thì URL có thể bị chặn/cho phép sai — cần test thêm khi có ca thật.
- Trang trả 403/429 (Cloudflare chặn UA desktop tĩnh) chỉ hiện ra là `không đọc được trang` CAO, crawler **không** retry và **không** đổi UA — cố đổi UA để lọt qua là việc đã tuyên bố không làm.
- `audit_html` chạy trên HTML **đã decode**; nếu server gửi charset sai, `probe` vẫn trả dict (không raise) nhưng text có thể lỗi dấu — finding lúc đó là hệ quả của encoding, không phải của on-page.
- Rule "alt rỗng hàng loạt" cần ngưỡng tự đặt (`word_count >= 200` và `>= 3` ảnh `alt=""`): trang ảnh dạng thư viện (nhiều ảnh, ít chữ) sẽ **không** bị nhắc, dù có thể nên nhắc. Đây là lựa chọn để tránh báo nhiễu, không phải chân lý.
- Crawl là **BFS đồng bộ một luồng**, không song song: site 100 trang với 10s/req worst case ~17 phút. **Đo thật 2026-10-14 trên nankybeauty.com: 20 trang/16.25 s (≈0.8 s/trang, exit 0)** ⇒ 100 trang thực tế ~80 s, không phải worst case; chưa đo với site có trang chết/timeout hàng loạt.
- Sitemap **index chỉ được mở 1 cấp và tối đa `SITEMAP_INDEX_MAX = 10` sitemap con**. Site có 20 file sitemap con sẽ thiếu trang (báo cáo ghi rõ "chỉ đọc 10 file..."), và `<sitemapindex>` lồng trong `<sitemapindex>` không được đệ quy — chủ đích, để một lần `--audit` không biến thành crawl cả thế giới.
- URL có đuôi `.xml` **không bao giờ** được audit như trang (đó là file sitemap, không phải trang HTML). Nếu một site thật sự phục vụ nội dung đọc được ở đuôi `.xml` thì rule on-page bỏ qua nó — chấp nhận, vì giá trị báo giả (CAO "thiếu title" cho một file XML) còn tệ hơn bỏ sót.

