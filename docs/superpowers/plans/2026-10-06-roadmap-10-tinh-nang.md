# Roadmap 10 tính năng — chia plan theo phase (2026-10-06)

> **Đây là roadmap master, KHÔNG phải implementation plan.** Theo scope check của quy trình viết plan: 10 tính năng = 10 subsystem độc lập → mỗi tính năng nhận **một plan riêng**, ship được phần mềm chạy được độc lập. Trước khi code mỗi tính năng phải qua: mini design trong chat (tính năng bounded) hoặc spec ngắn (tính năng architectural) → duyệt → implementation plan theo template GSC client (`2026-10-04-gsc-client.md`).
>
> **For agentic workers:** Đừng thực thi file này trực tiếp. Mở card của tính năng được chọn, làm design/spec trước, rồi mới viết plan chi tiết cho tính năng đó.

**Mục tiêu tổng:** biến tool từ "chạy tay + xem log" thành hệ thống SEO vận hành được hằng ngày — dữ liệu đã thu (rank history, GSC, session) phải được dùng để làm gì tiếp.

---

## Nguyên tắc chia phase

1. **Nhẹ trước, nặng sau**: tính năng ăn trên dữ liệu sẵn có làm trước; tính năng đụng kiến trúc (multi-site) để cuối.
2. **Mỗi phase có milestone dùng được thật** — hết phase là có thứ gì đó thay đổi cách vận hành, không phải nửa chừng hai tính năng.
3. **Không refactor kiểu "dịp tốt"**: `ui.py` 44KB không nằm trong roadmap nào cả; chỉ chia nhỏ khi một tính năng bắt buộc phải sửa file đó (lúc đó chia trong plan của tính năng đó).
4. **TDD theo pattern repo**: test là script assert thuần `_quick_*.py` ở root (gitignored), KHÔNG dùng pytest — copy pattern `_quick_gsc_test.py`.

## Bảng tổng quan

| Phase | Chủ đề | Tính năng | Effort ước lượng | Milestone |
|---|---|---|---|---|
| **1** | Khai thác dữ liệu sẵn có | F1 Export CSV · F2 Pipeline keyword GSC · F3 Cảnh báo tụt hạng | 4–6 phiên | Mọi dữ liệu đã thu xuất ra được + tự báo động |
| **2** | Tự động hóa vận hành | F4 Scheduler · F5 Proxy pool | 4–5 phiên | Rank/GSC/traffic chạy hằng ngày không cần mở GUI |
| **3** | Công cụ SEO chủ động | F6 Site audit · F7 Backlink auto-check · F8 Content generation Ollama | 6–9 phiên | Phần "80%" chuyển từ bảng tĩnh sang công cụ chủ động |
| **4** | Kiến trúc mở rộng | F9 AEO tracking · F10 Multi-site | 5–8 phiên | Scale được nhiều site + đo AI visibility |

*Effort "phiên" = một buổi làm việc chạy xong 1 implementation plan (~1–2 giờ). Số thô, đủ để so thứ tự, không phải cam kết.*

## Bản đồ phụ thuộc (tóm tắt)

- **F3 ↔ F4**: cảnh báo (F3) và scheduler (F4) ghép tự nhiên — scheduler chạy check định kỳ → rules engine của F3 gửi tin. Làm F3 trước để F4 có thứ để kích hoạt.
- **F6, F7 tái dùng F1**: kết quả audit / backlink check xuất CSV theo cùng module của F1.
- **F8 ăn F2**: content generation dùng danh sách từ khóa đã track/đề xuất làm đầu vào.
- **F10 đụng mọi thứ**: để cuối cùng. Nếu chắc chắn làm trong ~3 tháng, có "hedging rẻ" ngay từ Phase 1 — xem card F10.

---

# Phase 1 — Khai thác dữ liệu sẵn có

## F1 — Export báo cáo CSV

**Trạng thái: ✅ XONG 2026-10-13** — `utils/exporter.py`, plan `2026-10-13-f1-export-csv.md`, test `_quick_export_test.py`.

**Mục tiêu:** rank history + GSC snapshot xuất thành CSV mở bằng Excel (kể cả Excel tiếng Việt — UTF-8 BOM).

**Phạm vi:** CLI `--export rank|gsc|all` + nút Export trong tab "📈 Xếp Hạng"; file ghi vào `reports/export_<ngày>_<loại>.csv`. **Ngoài phạm vi:** xlsx thật (cần thư viện), PDF, chart ảnh.

**Quyết định cần chốt lúc mini design:** module `csv` stdlib (không thêm pandas — YAGNI); một CSV mỗi loại dữ liệu hay một file gộp 2 sheet-khả-năng.

**Chia task gợi ý (3 task):** (1) serializer rank history → rows CSV, test thuần với history giả; (2) serializer GSC snapshot → CSV, tương tự; (3) wire CLI `--export` + nút GUI + ghi file có BOM.

**Tiêu chí hoàn thành:** file mở Excel không lỗi font tiếng Việt; history rỗng → file chỉ có header, không crash; mỗi lần export ghi file mới, không ghi đè file cũ cùng ngày.

## F2 — Pipeline keyword từ GSC

**Trạng thái: ✅ XONG 2026-10-13** — `config/keywords.json` + `utils/keywords.py`, plan `2026-10-13-f2-keyword-pipeline.md`, test `_quick_keyword_test.py`.

**Mục tiêu:** mục "Query mới phát hiện" trong báo cáo gộp thành đầu vào thật: query có impressions đủ ngưỡng mà chưa track → đề xuất, xác nhận → thêm vào danh sách từ khóa.

**Phạm vi:** hàm đề xuất (filter impressions ≥ X trong lookback), CLI in gợi ý + `--gsc-add-keyword "query"` ghi vào cấu hình, nút "+ Thêm vào theo dõi" trong GUI. **Ngoài phạm vi:** tự động thêm không hỏi; đo volume từ nguồn ngoài (Ahrefs/SEMrush).

**Quyết định cần chốt (quan trọng nhất của Phase 1):** `SEO_KEYWORDS` đang hardcode trong `config/settings.py`. Nên chuyển sang `config/keywords.json` (một site vẫn đọc được, chuẩn bị sẵn cho F10) hay giữ nguyên settings.py? Khuyến nghị: chuyển sang `config/keywords.json` — đây là thay đổi nhỏ mở đường, làm một lần tại đây.

**Chia task gợi ý (4 task):** (1) nếu chốt chuyển — di chuyển keywords sang `config/keywords.json`, mọi chỗ đọc qua 1 hàm duy nhất; (2) hàm đề xuất thuần (input: GSC snapshot + danh sách đang track → output: list đề xuất), test fold dấu tiếng Việt tái dùng pattern NFD của gsc_client; (3) lệnh `--gsc-add-keyword` (xác nhận trước khi ghi, chống trùng khi so fold-dấu); (4) nút GUI trong tab Xếp Hạng.

**Tiêu chí hoàn thành:** query có dấu/không dấu vẫn nhận ra là trùng; keyword đã track không bị đề xuất lại; thêm xong, rank tracker check được kw mới ở lần chạy sau; file keywords luôn valid JSON sau khi ghi.

## F3 — Cảnh báo tụt hạng

**Trạng thái: ✅ XONG 2026-10-13 (code) — còn 1 bước phía owner:** `utils/alerts.py` + hook trong rank check, plan `2026-10-13-f3-rank-alerts.md`, test `_quick_alert_test.py` (59 test, sender mock). Chưa có tin Telegram **thật** cho tới khi owner tạo bot và cấp token/chat id theo `docs/SETUP_ALERTS.md`; `ALERTS_ENABLE` vẫn đang `False`.

**Mục tiêu:** hạng rơi quá N vị trí hoặc rớt khỏi Top 10 → gửi Telegram (fallback: in console). Là bộ não cảnh báo dùng chung, sau này scheduler (F4) chỉ cần gọi.

**Phạm vi:** rules engine thuần (input: lịch sử hạng → output: danh sách cảnh báo), Telegram sender qua `requests`, hook vào lúc rank check / GSC fetch xong, CLI `--alerts` xem lại cảnh báo đã gửi. **Ngoài phạm vi:** email SMTP, Slack/Discord, cảnh báo GSC CTR bất thường (để phase sau nếu cần).

**Quyết định cần chốt:** Telegram bot (dễ nhất, miễn phí — user cần tạo bot qua @BotFather 1 lần, hướng dẫn 5 dòng trong README); so sánh với lần check trước hay trung bình 3 lần gần nhất (khuyến nghị: lần trước + ngưỡng `RANK_ALERT_DROP = 5`); chống spam — tối đa 1 tin/ngày/từ khóa.

**Chia task gợi ý (4 task):** (1) rules engine thuần — test với history giả: rỗng/1 điểm → không cảnh báo, rơi 5 hạng → đúng 1 cảnh báo, rớt khỏi Top 10 → cảnh báo riêng; (2) Telegram sender (token/chat id trong settings, không in token ra console, lỗi network không crash flow chính); (3) hook sau rank check + GSC fetch; (4) CLI `--alerts` + nút "Gửi thử cảnh báo" trong GUI.

**Tiêu chí hoàn thành:** tắt config (`ALERTS_ENABLE = False`) → không gửi gì; một kw tụt chỉ nhận đúng 1 tin trong ngày dù check nhiều lần; Ollama/GSC/rank flow không bị chết khi Telegram sập.

---

# Phase 2 — Tự động hóa vận hành

## F4 — Scheduler tự động

**Mục tiêu:** rank check 3 lần/ngày, GSC fetch 4 lần/ngày, traffic session vào peak hours — chạy nền không cần mở GUI; GUI (nếu mở) chỉ xem trạng thái.

**Tính chất: architectural** — cần spec ngắn trước (state scheduler, lock chống chạy song song, hành vi khi máy tắt). Phần còn lại của Phase 2 là bounded.

**Quyết định cần chốt lúc spec:** (a) scheduler là process riêng `python main.py --schedule` headless (khuyến nghị) hay nằm trong GUI process — riêng thì chạy được khi đóng GUI, GUI chỉ đọc file state; (b) chống chạy song song GUI + scheduler: **lock file** bắt buộc, ai giữ lock người đó chạy; (c) máy tắt lỡ giờ → không bù, chạy lần kế tiếp (đơn giản, YAGNI); (d) tái dùng `can_run_*`/`mark_*` của rate_limiter, gsc_client, rank_tracker — scheduler KHÔNG tự giới hạn lại.

**Chia task gợi ý (5 task):** (1) scheduler core thuần — tính next_run cho từng job từ config, test không cần sleep thật; (2) vòng lặp chạy + ghi `scheduler_state.json` (last_run, next_run từng job); (3) lock file chống chạy 2 process; (4) CLI `--schedule` + `--schedule-status`; (5) GUI: nhãn trạng thái "Scheduler: chạy / dừng, lần rank kế: 14:32" (read-only).

**Tiêu chí hoàn thành:** restart scheduler không chạy lại job đã chạy hôm nay (đọc state); GUI đang chạy traffic → scheduler vẫn check rank bình thường (khác luồng, không đụng session state của traffic); tắt scheduler không làm hỏng state của rate limiter.

## F5 — Proxy pool + health check

**Mục tiêu:** danh sách proxy xoay vòng theo session, tự đánh dấu proxy chết, ưu tiên IP VN — giảm CAPTCHA trực tiếp (pain số 1 theo README).

**Phạm vi:** pool class (xoay vòng, cooldown, hồi phục), health check nhẹ, tích hợp vào browser_manager + rank_tracker, ô nhập list proxy + hiển thị trạng thái trong GUI. **Ngoài phạm vi:** mua/quản lý proxy tự động, proxy xoay từng request (chỉ xoay theo session).

**Quyết định cần chốt:** format dòng proxy (giữ format `host:port:user:pass` hiện có của `PROXY_LIST` — kiểm tra phần parse sẵn trong browser_manager trước khi viết plan); proxy chết sau N fail liên tiếp (khuyến nghị 3), hồi phục thử lại sau 24h; hết proxy sạch → dừng với thông báo rõ ràng, chỉ chạy không proxy nếu config cho phép.

**Chia task gợi ý (4 task):** (1) pool class thuần (xoay, đánh dấu chết, hồi phục) — test thuần không network; (2) health check (request nhẹ tới google.com qua proxy, timeout 10s); (3) tích hợp browser_manager (traffic) + rank_tracker (dùng riêng proxy sạch nhất); (4) GUI: textarea nhập list + nhãn "5/7 proxy sống".

**Tiêu chí hoàn thành:** 1 proxy chết không dừng luồng — tự xoay sang proxy kế; pool rỗng → hành vi y như hiện tại (không breaking change); trạng thái proxy sống qua restart (lưu file).

---

# Phase 3 — Công cụ SEO chủ động

## F6 — Site audit on-page

**Mục tiêu:** crawl site mục tiêu (≤ N trang cùng domain) kiểm tra title/meta description/H1/alt ảnh/thứ tự heading/canonical/robots/link hỏng; Core Web Vitals qua PageSpeed Insights API (miễn phí, quota không key là đủ dùng).

**Phạm vi:** CLI `--audit` + xuất CSV (tái dùng module F1) + nút GUI; báo cáo mỗi lỗi kèm severity (CAO/TRUNG BÌNH/THẤP) và URL bị lỗi. **Ngoài phạm vi:** audit JS-rendered sâu (requests đọc HTML tĩnh là đủ cho site WordPress/WooCommerce), so sánh 2 lần audit.

**Quyết định cần chốt:** crawler bằng `requests` + parser HTML (thêm dependency `beautifulsoup4` — nhẹ, không cần Playwright cho việc này); hàng đợi trang lấy từ `sitemap.xml`, fallback crawl theo link nội bộ; giới hạn 100 trang/lần audit.

**Chia task gợi ý (5 task):** (1) crawler thu thập (URL queue, chỉ cùng domain, tôn trọng robots.txt) — test với HTML cục bộ giả; (2) nhóm rule title/meta/H1 — mỗi hàm nhận HTML string, test offline; (3) nhóm rule ảnh/canonical/link hỏng; (4) PageSpeed fetch (mobile + desktop, lưu điểm + chỉ số); (5) báo cáo console + CSV + CLI/GUI wiring.

**Tiêu chí hoàn thành:** site 50 trang xong ~2 phút; link hỏng không làm treo audit (timeout 10s/link); không bao giờ request ra ngoài domain mục tiêu; site không có sitemap → vẫn audit được bằng crawl.

## F7 — Backlink auto-check

**Mục tiêu:** mỗi backlink trong `backlinks/tracker.py` được verify thật: còn sống (HTTP 200)? trang có chứa link tới site không? dofollow/nofollow? anchor text gì? — kèm import danh sách link ngoài từ GSC.

**Phạm vi:** verifier chạy theo batch, lưu `backlink_status.json` kèm ngày check, báo cáo % sống/chết + xuất CSV; import CSV "External links" tải tay từ UI Search Console (API của GSC **không** có endpoint external links — ghi rõ trong hướng dẫn). **Ngoài phạm vi:** tự tìm backlink mới ngoài GSC, đo DA/DR (cần API trả phí).

**Quyết định cần chốt:** fetch bằng `requests` + User-Agent browser thật; link bị coi là "có" khi `<a href>` chứa domain mục tiêu (so fold-dấu + chuẩn hóa www); link chết không đếm vào mục tiêu 20 backlink/tháng.

**Chia task gợi ý (4 task):** (1) verifier thuần — input: HTML string + domain → output: status; test với HTML mẫu (có link, nofollow, redirect, không có link); (2) fetch batch song song nhẹ (ThreadPool 5 luồng, timeout 15s, theo dõi redirect tới đích cuối); (3) lưu state + báo cáo + CSV; (4) importer CSV GSC + CLI `--backlink-check`.

**Tiêu chí hoàn thành:** trang 404 → đánh dấu chết ngay; timeout không treo cả batch; chạy lại trong ngày → dùng cache, không refetch (giống pattern snapshot GSC).

## F8 — Content generation bằng Ollama

**Mục tiêu:** chọn một mục trong content plan 30 ngày → sinh outline → draft bài tiếng Việt tối ưu từ khóa (lấy từ danh sách đang track) → lưu markdown vào `content/drafts/`.

**Phạm vi:** pipeline plan→outline→draft, frontmatter (từ khóa, ngày, loại content), kiểm tra SEO tự động thô (kw có trong title/H1/2 lần đầu), CLI `--generate "từ khóa"` + nút trong tab 🤖 AI Engine. **Ngoài phạm vi:** đăng bài tự động (WordPress API — để sau), sinh ảnh, sinh hàng loạt cả tháng trong 1 lần chạy.

**Quyết định cần chốt:** model `qwen3:30b-a3b` theo README; mỗi bước gọi `/api/generate` không stream (đơn giản, timeout 300s vì model 30b chậm); draft người dùng duyệt trước khi dùng — tool chỉ sinh, không tự đăng.

**Chia task gợi ý (4 task):** (1) prompt builder thuần — input: từ khóa, loại content, tuần trong plan → output: prompt string, test assert các mảnh bắt buộc có mặt; (2) Ollama client (kiểm tra kết nối trước, retry 1 lần khi timeout, lỗi → thông báo tiếng Việt rõ); (3) pipeline 2 bước outline→draft + ghi file UTF-8; (4) CLI + nút GUI hiển thị tiến trình.

**Tiêu chí hoàn thành:** Ollama tắt → thông báo "chưa chạy Ollama tại <url>" và không crash; bài sinh ra có đủ frontmatter + lưu đúng thư mục; chạy 2 lần cùng kw → 2 file khác nhau (không ghi đè).

---

# Phase 4 — Kiến trúc mở rộng

## F9 — AEO tracking (đo AI visibility)

**Mục tiêu:** theo từng từ khóa, hỏi các AI engine "câu trả lời có nhắc đến brand/domain X không?" → lưu `aeo_history.json` song song rank history, hiển thị cạnh cột SERP/GSC trong báo cáo gộp.

**Tính chất: architectural** — cần spec ngắn trước, đặc biệt phần nguồn dữ liệu.

**Quyết định cần chốt lúc spec (quan trọng nhất):** nguồn trả lời AI. Phương án: (a) browser Playwright hỏi Perplexity/Gemini web — dùng lại anti-detect + profile hiện có, không cần API key, nhưng dễ CAPTCHA nhất; (b) API có key (OpenAI/Gemini API) — ổn định nhưng trả phí + không phản ánh search thật; (c) hỗ trợ 1 engine trước (khuyến nghị Perplexity web — người dùng hay hỏi nó nhất khi mua sắm). Rate limit riêng: 1 lần/ngày/từ khóa/engine.

**Chia task gợi ý (4 task):** (1) lưu trữ + báo cáo AEO thuần (input: câu trả lời text + brand → output: nhắc/không, vị trí nhắc) — test với câu trả lời mẫu có/không có brand; (2) engine đầu tiên qua browser; (3) CLI `--aeo` + history; (4) cột "AI" trong báo cáo gộp.

**Tiêu chí hoàn thành:** CAPTCHA → dừng engine đó, các engine/kw khác vẫn chạy; brand viết thường/có dấu vẫn nhận ra; tắt AEO → báo cáo gộp y như cũ (không breaking).

## F10 — Multi-site / multi-project

**Mục tiêu:** quản lý nhiều site; mỗi site có URL, danh sách từ khóa, rank/GSC/session/AEO history, GSC property, profile browser riêng.

**Tính chất: architectural rõ ràng** — spec đầy đủ + script migration. Đặt cuối vì đụng mọi nơi đọc/ghi state.

**Quyết định cần chốt lúc spec:** layout `data/<site_slug>/` chứa mọi file json state; profiles tách theo site; registry site ở `config/sites.json`; CLI `--site <slug>`; GUI dropdown chọn site; script migration 1 lần chuyển dữ liệu nankybeauty hiện có.

**Hedging rẻ từ Phase 1:** nếu chắc chắn làm F10 trong ~3 tháng, thì từ F1–F3 khi tạo file state mới, ghi vào `data/` thay vì root project và đặt hàm đọc/ghi path qua 1 điểm duy nhất — migration sau chỉ là di chuyển folder, không phải sửa code khắp nơi. Không làm thêm gì khác (YAGNI).

**Chia task gợi ý (5 task):** (1) site registry + hàm context path duy nhất; (2) migration script + chạy cho nankybeauty; (3) chuyển rank/gsc/session/aeo đọc ghi qua context; (4) CLI `--site`; (5) GUI dropdown + hiển thị site đang chọn.

**Tiêu chí hoàn thành:** 2 site chạy xen kẽ không lẫn dữ liệu; site nankybeauty sau migration chạy đúng như trước migration; thiếu tham số site khi có >1 site → lỗi nhắc người dùng chọn thay vì chọn giùm âm thầm.

---

## Quy trình thực hiện từng tính năng (áp dụng cho mọi card)

1. **Mini design trong chat** (bounded) hoặc **spec ngắn** (`docs/superpowers/specs/`, architectural: F4, F9, F10) → chờ duyệt.
2. **Implementation plan riêng** (`docs/superpowers/plans/YYYY-MM-DD-<tên>.md`) theo template `2026-10-04-gsc-client.md` — goal, global constraints, review focus, task có test trước.
3. Thực hiện theo plan: TDD pattern `_quick_*.py`, commit mỗi task.
4. Cập nhật README + bảng cấu hình trong README sau mỗi tính năng có thêm setting.

## Thứ tự chạy khuyến nghị

**F1 → F2 → F3 → F4 → F5 → F6 → F7 → F8 → F9 → F10**

Điểm có thể dừng đánh giá lại: sau F3 (Phase 1 xong — đã đáng giá dùng hằng ngày), sau F5 (vận hành tự động hoàn chỉnh), sau F8 (Phase 3 xong). Phase 4 chỉ bắt đầu khi Phase 1–3 ổn định trong thực tế.
