# F7 — Backlink auto-check Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development / executing-plans. Bước theo checkbox.

**Goal:** `python main.py --backlink-check` verify **thật** từng backlink trong danh sách của owner: trang đích còn sống (HTTP)? trên trang **có** link tới site mục tiêu không? `rel` là dofollow hay nofollow/sponsored/ugc? anchor text là gì? — lưu state có ngày check, chạy lại trong ngày dùng cache, in báo cáo `% sống / % có link / dofollow` và xuất CSV bằng đúng mạch F1. Kèm `--backlink-import <file.csv>` cho danh sách "External links" tải tay từ Search Console.

**Architecture:** 2 module, mỗi lớp test được không cần network:
`utils/backlinks.py` (store `config/backlinks.json` + state `data/backlink_status.json` + **hàm verify thuần** `verify_page(url, html, status, target_domain)` — tái dùng `utils/html_probe.probe` chứ không parse lại) →
`utils/backlink_checker.py` (fetch batch `requests` + ThreadPool, cache theo ngày, gom kết quả, báo cáo, `audit_rows`-style rows cho CSV) → CLI/GUI/exporter.

**Tech Stack:** Python 3.11 stdlib (`json`, `os`, `csv`, `concurrent.futures`, `urllib.parse`) + `requests` (đã có trong requirements.txt). **Không** thêm dependency, **không** Playwright (backlink là HTML tĩnh của trang người khác).

**Spec:** không có file spec riêng — card F7 (roadmap dòng 131) là bounded, mọi quyết định nằm ở mục "Quyết định đã chốt".

## Global Constraints

- **Không có backlink thật trong repo.** `backlinks/tracker.py` chỉ là danh sách **cơ hội** (`status: "todo"`, URL là homepage của facebook.com/toplist.vn...), không phải link đã đặt. Verify mấy URL đó thì 100% báo "không có link tới site" — vô nghĩa. Nguồn link để check là `config/backlinks.json` (owner thêm tay / import GSC), **không** phải `BACKLINK_OPPORTUNITIES`.
- **Chỉ đọc trang công khai, lịch sự.** Tối đa `BACKLINK_PARALLEL = 5` luồng, `BACKLINK_TIMEOUT = 15` s, **một request mỗi URL mỗi lần chạy**, UA desktop tĩnh `AUDIT_USER_AGENT` (tái dùng, không đặt UA mới), **không** retry để lách 403, **không** đổi UA, **không** giải CAPTCHA, **không** đụng lớp anti-detect. Đây là trang của người khác: vượt 403/429 thì ghi "bị chặn" rồi đi tiếp, không cố vào.
- HTTP 404/410/5xx/timeout **là dữ liệu**: `status` lưu vào state, batch không dừng, không raise.
- **Cache trong ngày**: URL đã check trong `BACKLINK_CACHE_HOURS` (mặc định 24) thì dùng lại kết quả, không refetch (đúng pattern snapshot GSC); `--backlink-refresh` mới refetch hết.
- "Có link" = host của `href` **trùng hoặc là subdomain** của domain mục tiêu (bỏ `www.`, hạ chữ thường) — so bằng hostname đã parse, **không** dùng `endswith` trên chuỗi (bẫy `nankybeauty.com.evil.io`).
- `dofollow` = link có mặt, `rel` **không** chứa `nofollow`/`sponsored`/`ugc`. Ba giá trị này lưu riêng để báo cáo nói được "nofollow mấy cái".
- State/store path đi qua **một hàm duy nhất** mỗi loại (`_store_path()`, `_state_path()`), đọc `cfg` tại lúc gọi — hedge F10 (di chuyển folder, không sửa code khắp nơi).
- CSV phải qua `utils/exporter.py` (`export_backlinks()` gọi `_unique_path("backlinks")` + `_write_csv`): **không** `csv.writer` ở module check; `backlink_checker.py` không import `csv`.
- Không in **lộ** token/key gì ở feature này (không có credential nào).
- Console Windows: module mới **không tự gọi `sys.exit`** — trả mã về cho CLI; in tiếng Việt an toàn vì `main.py` đã reconfigure UTF-8 (F4).
- Test `_quick_backlink_test.py` ở root (gitignored), assert thuần, **không pytest, không network** (fetcher tiêm vào), chạy với `PYTHONIOENCODING=utf-8`.
- Mỗi task một commit.

## Review Focus

1. `verify_page` với HTML có 2 link tới site (1 dofollow, 1 nofollow) → `has_link=True`, `dofollow=False`? (chọn theo link "tệ nhất" hay "tốt nhất"? — phải chốt: **report theo link tốt nhất**, chi tiết ghi số link nofollow).
2. Host match: `https://www.nankybeauty.com/` ✓, `//nankybeauty.com` ✓, `https://blog.nankybeauty.com` ✓, `https://nankybeauty.com.evil.io/` ✗, `https://evil.io/?to=nankybeauty.com` ✗ (query không phải host), `mailto:a@nankybeauty.com` ✗ (không phải link nhúng được).
3. Anchor text rỗng (`<a href><img></a>`) → `anchor=""` nhưng vẫn tính là link; anchor gấp đôi whitespace phải normalize.
4. Cache: chạy 2 lần cùng ngày → fetcher gọi **1** lần; `--backlink-refresh` → 2 lần; state hỏng JSON → coi như chưa có gì (không raise).
5. ThreadPool: một URL raise trong fetcher → phần còn lại vẫn xong, URL đó có `error` (không mất trang khỏi báo cáo).
6. Deadline: `BACKLINK_PARALLEL` đổi được, `max_workers` không được vượt số URL (đừng spawn 5 luồng cho 1 link).
7. Importer CSV GSC: GSC đổi schema theo thời gian → parser phải tìm cột có giá trị là URL, không hardcode tên cột; file không có cột nào → thông điệp rõ, exit 2, store không bị xoá.

## Quyết định đã chốt

| Câu hỏi | Chốt | Lý do |
|---|---|---|
| Nguồn link để check | `config/backlinks.json` (owner thêm tay / import GSC) | `backlinks/tracker.py` là danh sách **cơ hội** ("todo"), không phải link đã đặt — verify nó thì chỉ báo giả. |
| Parser link | tái dùng `utils/html_probe.probe` (F6) | đã có `links[{href,text,rel}]` + chuẩn hóa whitespace, không parse hai lần, không thêm dependency. |
| Fetch | `requests` + ThreadPool ≤ 5 luồng, timeout 15 s | card yêu cầu "batch song song nhẹ"; 5 luồng là mức lịch sự với site người khác. |
| Cache | 24 h/URL trong `data/backlink_status.json` | tiêu chí "chạy lại trong ngày không refetch". |
| Link "có" | host trùng hoặc subdomain của domain mục tiêu | card ghi "so fold-dấu + chuẩn hóa www"; host-parse đúng hơn chuỗi endswith (chặn `d.com.evil.io`). |
| Ngoài phạm vi | DA/DR (API trả phí), tự tìm backlink mới, tự đặt link, đo Google Analytics | theo card. |
| "20 backlink/tháng" | **không** tự đếm lại trong tracker | con số đó đang đếm **cơ hội**, không đếm link sống; báo cáo F7 nói số link sống/chết thật, README ghi rõ hai thứ khác nhau. |

---

### Task 1: `utils/backlinks.py` — store + state + verify thuần

**Files:** Create `utils/backlinks.py`, Modify `config/settings.py` (PHẦN I), Create `_quick_backlink_test.py`.

**Interfaces (Produces):** `load_links() -> list[dict]` (`{"url","note","added"}`), `add_link(url, note="") -> (bool, str)`, `remove_link(url) -> (bool, str)`, `save_links(list)`, `target_domain() -> str`, `verify_page(url, html, status, domain) -> dict` (`{"url","status","has_link","dofollow","links_to_target","anchors","rel_seen","error"}`), `load_state()/save_state(state)`, `is_fresh(entry, hours) -> bool`, `_store_path()`, `_state_path()`.

- [x] Step 1 — Test fail trước: store đọc dict/list trần/thiếu file/mã hỏng; `add_link` chống trùng theo host+path đã normalize, từ chối không http; verify_page 6 case ở Review Focus 2; anchor normalize; rel nhiều giá trị (`"nofollow noopener"`); 2 link 1 dofollow 1 nofollow → `dofollow=True` (link tốt nhất thắng) + `rel_seen` liệt kê đủ; state round-trip + `is_fresh` (23 h = tươi, 25 h = cũ, ngày sai dạng = cũ); AST cấm `requests`/`csv`/`open` ngoài các hàm store/state.
- [x] Step 2 — Chạy → FAIL (`ModuleNotFoundError: No module named 'utils.backlinks'`).
- [x] Step 3 — Implement (mirror `utils/keywords.py`: import lười, không kéo requests ở đầu file).
- [x] Step 4 — Test → ALL PASS + CJK scan 0 + mutation battery.
- [x] Step 5 — Commit: `feat: F7 backlink store + verify thuan (html_probe tai dung, khong dependency)`

**Kết quả Task 1 (2026-10-14):** 26 test ALL PASS, CJK 0, mutation **19/19 CAUGHT**, restore byte-exact.
7 suite cũ chạy lại nguyên xanh sau khi sửa `html_probe` (audit 104/104).

**Deviations so với plan:**
1. `verify_page` trả thêm `final_url`, **không** có key `error` — lỗi là chuyện của tầng fetch (Task 2); hàm thuần không có gì để mà lỗi.
2. `verify_page(url, html, status, domain, final_url="")` — tham số thứ năm vì href tương đối phải resolve theo trang **thực sự** đã đọc (sau redirect), không theo URL owner khai.
3. Chống trùng mạnh hơn plan: `_link_key` bỏ cả scheme, fragment, dấu gạch cuối **và tham số tracking** (`utm_*`, `gclid`, `fbclid`, `ref`...) — `?utm_source=fb` của cùng một trang từng bị tính là hai backlink.
4. Store/state dùng `urljoin` + parse host thay vì so chuỗi; `mailto:`/`tel:`/`javascript:` loại vì scheme không phải http(s) sau khi resolve.
5. Đường dẫn store **được gitignore** (`config/backlinks.json`): danh sách site đang đặt link là dữ liệu kinh doanh, repo này public — khác `config/keywords.json` (tracking data để ship mẫu).
6. **Sửa `utils/html_probe.py` (F6, không phải F7):** `_Probe` chỉ đẩy link lên `links[]` khi gặp `</a>`, và `<a>` mới ghi đè `<a>` đang mở. Trang HTML thiếu `</a>` — lỗi cực phổ biến — vì thế bị bỏ sót link. Với audit F6 đó chỉ là lệch một con số liên kết, nhưng với F7 nó biến một backlink **đã trả tiền đặt** thành "chết". Thêm `_flush_link()` gọi khi mở `<a>` mới và khi `close()`. Blast radius đã đo: `links[]` chỉ khác với HTML hỏng thẻ, 104 test audit vẫn xanh, mutation "probe: flush khong chong the a trong" bị cả hai harness bắt.

**Hai mutation round 1 sống → thành test, không phải code chết:**
- `host.endswith(target)` (bẫy nhận vơ) không bị bắt vì fixture chỉ có `nankybeauty.com.evil.io` (đuôi là `.evil.io`). Thêm `khongphanankybeauty.com` — đuôi **đúng bằng** target nhưng bị nối thêm ở đầu.
- Bỏ kiểm tra scheme trong `_valid_url` không bị bắt vì `ftp://b.vn/x` có cùng chìa host+path với `https://b.vn/x` đã thêm trước đó → nhánh chống trùng che nhánh từ chối scheme. Thêm `test_add_link_rejects_non_http_schemes_on_a_clean_store` chạy trên store rỗng.


### Task 2: `utils/backlink_checker.py` — batch fetch + cache + báo cáo

**Files:** Create `utils/backlink_checker.py`, Modify `_quick_backlink_test.py`.

**Interfaces:** `check_links(links, state, fetcher=None, refresh=False, now=None) -> (new_state, report_rows)`; `default_fetcher(url) -> (status, html, final_url)`; `_pool_size()`; `format_report(rows) -> str`; `run_backlink_check_cli(limit=None, refresh=False, url="") -> int`; `check_rows(rows) -> (header, rows)` cho exporter.

- [x] Step 1 — Test fail trước (fake fetcher đếm lời gọi): mọi URL có mặt trong báo cáo kể cả URL lỗi; `max_workers` ≤ số URL; 404 → `status=404, has_link=False, error=""`; timeout/exception → `status=0, error=<tên exception>`; final_url khác host (redirect sang domain khác) vẫn verify trên HTML trả về nhưng ghi `final_url`; URL tươi trong cache + `refresh=False` → fetcher **không** được gọi; `refresh=True` → gọi lại; quá `limit` thì cắt, báo cáo ghi "còn N link chưa check"; rỗng → exit 2 + hướng dẫn `--backlink-add`.
- [x] Step 2 — Chạy → FAIL (16 test Task 2 ERROR `No module named 'utils.backlink_checker'`, 26 test Task 1 vẫn PASS — RED sạch, không lan).
- [x] Step 3 — Implement ThreadPool + cache.
- [x] Step 4 — Test ALL PASS + mutation.
- [x] Step 5 — Commit: `feat: F7 backlink batch check (ThreadPool 5, cache 24h, loi la du lieu)`

**Kết quả Task 2 (2026-10-14):** 45 test ALL PASS (thêm 19 test cho checker), mutation **21/21 CAUGHT**, restore byte-exact, 7 suite cũ nguyên xanh.

**Deviations so với plan:**
1. `check_links(...)` nhận thêm `domain=None` — CLI truyền `bl.target_domain()`, test truyền DOMAIN tường minh nên không phải sửa `cfg.TARGET_URL` giả.
2. `fetcher` là tham số tiêm được ở **cả** `check_links` và `run_backlink_check_cli` — giống `crawl(fetcher=)` của F6, nhờ vậy CLI test được mà không đụng network.
3. `_fetch_one` bắt MỌI exception (kể cả fetcher trả về shape sai) -> `status=0, error="TypeName: message"` (clip 120 ký tự). Link lỗi vẫn là một dòng báo cáo, không bao giờ biến mất.
4. **Pruning state đặt ở CLI, không ở `check_links`**: `check_links` merge vào state cũ để `--backlink-limit` không xóa cache của những link chưa check; CLI mới là nơi đối chiếu với danh sách đầy đủ (`known`) và bỏ entry của link đã bị owner xóa — nhờ vậy `--export backlinks` không liệt kê link không còn trong danh sách.
5. `default_fetcher` **không** `raise_for_status`, **không** retry, **không** đổi UA — test `test_default_fetcher_one_polite_request_no_retry_no_ua_swap` đếm đúng 1 lời gọi `requests.get` và kiểm tra timeout/UA/allow_redirects lấy từ PHẦN I + `AUDIT_USER_AGENT`.
6. Header CSV nằm trong checker (`CSV_HEADER`) vì checker là nơi biết row shape; exporter chỉ ghi (Task 3).
7. Report có thêm dòng cảnh báo riêng cho "link không đọc được (lỗi FETCH)" tách khỏi "link chết" — 404 và timeout không được gộp một nhóm, owner cần biết cái nào phải check lại.

**Hai mutation round 1 sống → thành test:** cả hai ở `format_report`. Kiểm tra chuỗi "2/3" hoặc "66.7%" rời rạc không phân biệt được số nào là ratio nào (dòng summary có ba cặp a/b), nên mutant đếm 404 vào nhóm "còn sống" và mutant chia `_pct(alive, linked)` đều qua mặt. Test mới parse `(a/b, nhãn, %)` thành dict theo nhãn rồi so từng nhãn.


### Task 3: CSV + importer CSV "External links" của GSC

**Files:** Modify `utils/exporter.py`, Modify `utils/backlink_checker.py`, Modify `_quick_backlink_test.py`.

**Interfaces:** `exporter.export_backlinks() -> (path, n)` (đọc state qua `backlinks.load_state()`, mapping thứ tự cột để một chỗ trong checker); `import_gsc_csv(path) -> (added:int, message:str)`.

- [ ] Step 1 — Test fail trước: header CSV **chốt một lần**: `["trạng thái", "url", "host", "có link", "dofollow", "số link", "anchor", "check lúc", "url cuối", "lỗi"]` (tiếng Việt có dấu, không có dấu cách thừa, thứ tự cố định để người dùng so hai lần export); AST chặn `import csv` trong checker; `_unique_path("backlinks")`; importer: tìm cột chứa URL **trong mọi ô** (GSC đổi tên cột theo thời gian — không hardcode header), **KHÔNG lọc theo domain** (backlink tới site mình nằm trên domain khác, giữ hết, chỉ bỏ ô không parse ra http(s) URL); trùng URL đã có → không thêm; file không có URL nào → message rõ + store giữ nguyên + exit 2; file có BOM (GSC export ghi BOM) phải đọc được.
- [ ] Step 2 — Chạy → FAIL.
- [ ] Step 3 — Implement.
- [ ] Step 4 — Test ALL PASS + mutation.
- [ ] Step 5 — Commit: `feat: F7 xuat CSV backlink + import CSV External links cua GSC`

### Task 4: CLI + GUI + README

**Files:** Modify `main.py`, `ui.py`, `README.md`, `backlinks/tracker.py` (chỉ docstring, ghi rõ cơ hội ≠ link đã đặt), Modify `_quick_backlink_test.py`.

- [ ] Step 1 — Test fail trước: `main.py` có `"--backlink-check"`, `"--backlink-add"`, `"--backlink-import"`, `"--backlink-refresh"` + help in đủ dòng (AST); GUI `btn_backlinks` + `run_backlink_check`; README needle `--backlink-check`, `config/backlinks.json`, `backlink_status.json`, `BACKLINK_PARALLEL`, "External links", "Cơ hội" vs "đã đặt"; bảng PHẦN I.
- [ ] Step 2 — Chạy → FAIL.
- [ ] Step 3 — Implement wiring.
- [ ] Step 4 — GUI: nút **🔗  CHECK BACKLINK** trong hàng nút tab 📈 Xếp Hạng (cùng pattern `_audit_running`: guard `is_running`, thread nền, tự xuất CSV xong in đường dẫn).
- [ ] Step 5 — README: mục **"### 13. Backlink auto-check"** (nguồn link, cache, CSV, importer, giới hạn "không đo DA/DR, không tự tìm link"), bảng PHẦN I, cây project + `data/backlink_status.json`.
- [ ] Step 6 — **Verify thật**: `--backlink-add https://nankybeauty.com/` (link nội bộ của chính site — sự thật HTTP kiểm được) rồi `--backlink-check` → exit 0, in `có link=True`, chạy lần 2 trong ngày → fetcher không gọi lại (cache); `--backlink-refresh` → gọi lại. **Ghi rõ chưa verify với backlink bên thứ ba thật vì owner chưa có danh sách link đã đặt** — không bịa URL để cho đẹp báo cáo.
- [ ] Step 7 — GUI probe (mainloop thật + stub network, như F6 Task 4 Step 7).
- [ ] Step 8 — Commit: `feat: F7 cli --backlink-check/add/import + nut GUI + README`

## Tiêu chí hoàn thành (card F7)

- Trang 404 → đánh dấu chết ngay.
- Timeout không treo cả batch (mỗi URL một request, timeout 15 s, exception → một dòng báo cáo).
- Chạy lại trong ngày → dùng cache, không refetch.
- Kết quả đọc được trên console + mở được bằng Excel (CSV BOM từ exporter).
- Import được CSV "External links" tải tay từ GSC (API GSC **không** có endpoint external links — ghi rõ trong README).

## Known limitations (ghi nhận, không sửa trong plan này)

- Không có DA/DR/traffic của trang đặt link (Ahrefs/Moz API trả phí — ngoài phạm vi card).
- Danh sách link **không tự lớn**: nếu owner không thêm tay hoặc import GSC, `--backlink-check` không có gì để check (exit 2 + hướng dẫn). GSC export chỉ chứa link Google **thấy**, không phải link thật sự còn trên web.
- Chỉ đọc HTML tĩnh: link render bằng JS (widget, lazy iframe) không được đếm.
- 403/429 (site chặn bot) → báo "bị chặn", **không** retry, **không** đổi UA — đó là lớp né phát hiện đã tuyên bố không làm.
- `dofollow` suy từ `rel`; một số CMS nofollow bằng JS/`<meta name=robots>` trên trang — không phát hiện.
- Check link **không** chứng minh link được Google index hay tính giá trị; nó chỉ trả lời "trang đó còn tồn tại và còn link tới site mình không".
