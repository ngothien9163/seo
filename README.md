# SEO Traffic Bot — AI Powered

Công cụ SEO toàn diện theo triết lý **80% Content & Backlink | 20% Automation**, viết bằng Python (Playwright + CustomTkinter). Project bao gồm hai phần:

- **80% — Chiến lược Content & Backlink**: content plan 30 ngày, keyword research, backlink tracker.
- **20% — Automation traffic**: mô phỏng người dùng thật truy cập website qua Google search, nuôi nick, tương tác onsite — với hàng loạt lớp chống phát hiện và giới hạn tần suất để giảm rủi ro bị Google phạt.

> ⚠️ **Lưu ý quan trọng**: Traffic automation là hành vi vi phạm chính sách của Google nếu lạm dụng. Tool này được thiết kế xoay quanh việc **giới hạn và tự nhiên hóa** (25 session/ngày, hành vi người thật, fingerprint đúng thiết bị), nhưng rủi ro penalty cho domain vẫn tồn tại. Phần Content & Backlink (80%) mới là nền tảng SEO bền vững — automation chỉ là chất xúc tác.

---

## Tính năng chính

### 1. Automation Traffic — 4 chế độ (`TRAFFIC_MODE`)

| Chế độ | Mô tả |
|---|---|
| `direct` | Truy cập thẳng site (kèm referer ngẫu nhiên Google/Bing/Facebook) |
| `search` | Search từ khóa trên Google → đọc SERP → click đúng link target (tự nhiên nhất) |
| `aio` | Hỏi Gemini/ChatGPT/Perplexity về target site trước, rồi mới search Google + click |
| `mix` | Xen kẽ ngẫu nhiên các chế độ trên |

Search flow có xử lý sẵn: popup consent Google, detect CAPTCHA (cả URL lẫn DOM), bóc tách redirect `/url?q=` của Google.

### 2. Anti-detect — Fingerprint chuẩn theo thiết bị thật

- Map fingerprint (GPU vendor/renderer, CPU cores, RAM, platform, plugins) cho từng máy: iPhone 14 Pro / 13 Mini / Pixel 7 / Pixel 5 / Galaxy S22 / iPad Pro 11.
- Script inject riêng cho từng nền tảng: iOS Safari (không có `window.chrome`, 0 plugin) vs Android Chrome; desktop dùng Intel Iris.
- Che `navigator.webdriver`, WebGL, permissions, `deviceMemory`, `hardwareConcurrency`; xóa dấu vết Playwright trong stack trace; tích hợp `playwright-stealth`.
- **Mobile 70% / Desktop 30%** (mặc định), hoặc chọn thiết bị cụ thể.
- Force `locale=vi-VN`, `timezone=Asia/Ho_Chi_Minh`, header `Accept-Language` tiếng Việt — tránh mismatch gây CAPTCHA.
- **Lưu profile** (cookie/localStorage) vào `profiles/` giữa các lần chạy → Google nhận ra "browser quen thuộc", giảm CAPTCHA. Hỗ trợ proxy (kèm user/pass).

### 3. Hành vi người thật

- **AI Persona engine**: mỗi session sinh persona ngẫu nhiên — mood (`hurried`/`curious`/`relaxed`) quy định tốc độ gõ, tỉ lệ gõ nhầm, tốc độ đọc, số click vào đối thủ trước khi vào target; hành vi search seed theo keyword để ổn định.
- **Warm-up trước Google** (tùy chọn): ghé 1 trang VN phù hợp giới tính persona (nữ → beauty/lifestyle, nam → báo chí) để tạo lịch sử duyệt.
- **Nuôi Nick** (warmup dài hạn): YouTube (xem video 15–30s), đọc báo VN, Wikipedia, Shopee/Tiki/Lazada, Facebook, Instagram — chạy 1–2 mode ngẫu nhiên mỗi lần.
- **Onsite interaction**: click CTA (tiếng Việt/Anh), đổi tab, xem gallery, fill form, search onsite, click link nội bộ, auto đóng popup, đi sâu 2–3 trang.
- **Keyword variation**: sinh biến thể từ khóa ("giá rẻ", "ở đâu tốt", "2025", "cách ..."...) để tránh search một mẫu lặp lại.
- **Mouse helper**: di chuột theo đường cong, scroll ngắt quãng ngẫu nhiên.

### 4. Giới hạn tần suất — chống bị Google soi

- **Tối đa 25 session/ngày**, cooldown tối thiểu 5 phút giữa các session; trạng thái lưu `session_state.json` (không reset khi restart).
- Stagger các luồng (5–25s), nghỉ ngẫu nhiên giữa session trong luồng (10–45s).
- **Peak hours VN** (9–11h, 14–16h, 19–22h): phân bổ nhiều session hơn vào khung giờ cao điểm.
- Cấu hình rủi ro: pogo-stick và third-page click **tắt mặc định**; comment tự động đã vô hiệu hóa vĩnh viễn (nguy cơ phạt nặng).

### 5. Chiến lược Content & Backlink (80%)

- **Content plan 30 ngày**: lịch blog/social/video/review theo 4 tuần — Giáo dục → Chuyên sâu → Authority → Chuyển đổi. Mục tiêu 30 bài/tháng.
- **Keyword research**: volume/difficulty/search intent + phân loại funnel TOFU (nhận thức) / MOFU (cân nhắc) / BOFU (quyết định).
- **Backlink tracker**: 15 nguồn backlink chia 3 tier theo độ khó + danh sách guest post target kèm DA. Mục tiêu 20 backlink/tháng, DA tối thiểu 20.

### 6. Rank Tracker — theo dõi vị trí từ khóa

- Search từng từ khóa trên Google (`num=100`, `hl=vi`, tắt cá nhân hóa) và tìm vị trí domain mục tiêu trong kết quả organic.
- Lưu lịch sử vào `rank_history.json` (tồn tại qua restart, giữ 90 lần check gần nhất).
- Báo cáo: hạng hiện tại, Δ so với lần trước (↑/↓/NEW/RỚT), sparkline xu hướng 8 lần gần đây, thống kê Top 3/Top 10/hạng trung bình.
- An toàn: tối đa 3 lần check/ngày, cooldown 1 giờ, xáo trộn thứ tự từ khóa, profile browser riêng "rank_tracker" (browser "quen thuộc" với Google), dừng ngay khi gặp CAPTCHA.
- Gặp CAPTCHA: CLI cho phép giải thủ công trong cửa sổ browser rồi Enter để tiếp tục; GUI hiện dialog Retry/Cancel. Dùng proxy (ô Proxy trong GUI hoặc `PROXY_LIST`) nếu IP đang bị Google gắn cờ.

### 7. Google Search Console — dữ liệu SEO thật qua API

- Lấy **clicks, impressions, vị trí trung bình, CTR** theo từng query trực tiếp từ Google (Search Analytics API) — không scrape, không CAPTCHA, không phụ thuộc IP.
- **Báo cáo gộp**: mỗi từ khóa hiển thị hạng SERP (Rank Tracker) cạnh dữ liệu thật từ Google; kèm mục "Query mới phát hiện" — các query người dùng tìm mà bạn chưa theo dõi (dữ liệu đầu vào cho keyword research).
- Snapshot lưu `gsc_history.json` (giữ 90 ngày), tối đa 4 lần fetch/ngày, xem lại không tốn quota.
- **Hạng dự phòng khi SERP CAPTCHA (T29)**: Google SERP đôi khi trả CAPTCHA → từ khóa đó không có hạng thật. Khi vậy, `--rank-report` / `--rank` và section SERP trong `--html-report` hiển thị **hạng trung bình GSC 28 ngày** với nhãn `~8 (GSC)` + dòng giải thích dưới bảng; GSC không có từ khóa đó thì giữ `>100` như cũ. **Chỉ hiển thị** — không ghi vào rank history (hạng SERP thật vẫn là nguồn thật, chạy lại `--rank` khi bớt CAPTCHA là tự mất nhãn). Chưa setup GSC → tính năng tự ẩn.
- Setup service account Google ~10 phút, làm 1 lần: xem **[docs/SETUP_GSC.md](docs/SETUP_GSC.md)**.

### 8. Xuất báo cáo CSV — mang dữ liệu đi nơi khác

- `--export rank` xuất **toàn bộ lịch sử xếp hạng** (một dòng mỗi lần check × mỗi từ khóa), `--export gsc` xuất các query của snapshot Search Console mới nhất, `--export audit` xuất các lỗi của lần `--audit` gần nhất, `--export backlinks` xuất kết quả check backlink, `--export plan` xuất **30 mục content plan + tiến độ** (đã push WP / draft chờ duyệt / chưa làm — dùng chung nguồn với `--plan-progress`), `--export outreach` (T50) xuất **sổ outreach** — URL/host/bài/contact/note/trạng thái/mốc update/số ngày chờ, xếp chú ý trước (proposed → dead) như `--outreach-list` — để mở Excel giao việc cho VA, `--export all` (mặc định) ra **cả 6 loại**, mỗi loại một file (nguồn nào chưa có dữ liệu thì file đó chỉ có tiêu đề, quy trình không gãy).
- Mã **UTF-8 có BOM** → mở trực tiếp bằng Excel bản tiếng Việt không lỗi dấu; CTR xuất dạng số đã ×100 (không kèm ký hiệu `%`) để Excel còn tính toán được.
- File ghi vào `reports/export_<ngày>_<giờ>_<rank|gsc|audit|backlinks|plan>.csv`, **mỗi lần export một file mới** — không ghi đè lần trước. Chưa có dữ liệu thì file vẫn được ghi (chỉ có dòng tiêu đề) để quy trình không gãy.
- GUI: tab **📈 Xếp Hạng** → nút **📤 XUẤT CSV** (in đường dẫn file ra log).

### 9. Từ khóa đề xuất từ Search Console — danh sách biết tự lớn

- Query người dùng thực sự tìm mà bạn **chưa theo dõi**, có impressions ≥ `KEYWORD_SUGGEST_MIN_IMPRESSIONS`, được liệt kê theo `--gsc-keywords` (kèm impressions/clicks/vị trí trung bình).
- Thêm bằng `python main.py --gsc-add-keyword "..."` (có bước xác nhận, `--yes` cho script) hoặc nút **+ Thêm** trong khung "Từ khóa đề xuất" ở tab 📈 Xếp Hạng (nút **💡 TỪ KHÓA ĐỀ XUẤT** nạp danh sách, tự làm mới sau mỗi lần lấy dữ liệu Search Console). Chống trùng theo dấu tiếng Việt: "noi mi quan 2" và "nối mi quận 2" là một.
- Danh sách từ khóa nằm trong **`config/keywords.json`** (`{"site", "keywords"}`), không còn hardcode trong settings.py — thêm từ khóa xong, lần `--rank` kế tiếp check luôn.
- Bảng "Query mới phát hiện" trong báo cáo gộp cũng trỏ thẳng tới lệnh này.

### 10. Cảnh báo tụt hạng — Telegram (hoặc console)

- Sau mỗi lần check xếp hạng, bộ cảnh báo so **2 lần check gần nhất**: hạng rơi **≥ `RANK_ALERT_DROP`** (mặc định 5) hoặc đang trong **Top 10 mà rớt ra ngoài** → một tin nhắn. Mỗi từ khóa **tối đa 1 tin/ngày**, dù bạn check 3 lần (`data/alerts_state.json`).
- Chạy **tự động** trong `--rank` và trong GUI (tab 📈 Xếp Hạng); `--gsc` chỉ nhắc "có N cảnh báo đang chờ" chứ không gửi trùng. Muốn xem chủ động: `python main.py --alerts`.
- Mặc định `ALERTS_ENABLE = False` → **không gửi đi đâu cả**, tin chỉ in ra console để bạn thấy thứ đáng lẽ đã gửi. Bật Telegram theo **[`docs/SETUP_ALERTS.md`](docs/SETUP_ALERTS.md)** (~5 phút, không cần server).
- Token nên để ở biến môi trường `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` (thắng giá trị trong settings.py) khỏi phải commit bí mật.
- Telegram sập / sai token / hết mạng → chỉ in cảnh báo lỗi, **rank check không chết theo**, và tin chưa gửi sẽ được thử lại ở lần check sau.
- GUI có nút **🧪 GỬI THỬ BÁO ĐỘNG** để xác nhận tin tới điện thoại, kèm nhãn "Cảnh báo: Telegram/console".
- **Cảnh báo sớm theo xu hướng (C4)**: ngoài rule so 2 lần check, engine còn nhìn **14 lần check gần nhất** (`RANK_ALERT_TREND_WINDOW`) — trung bình hạng của 4 mốc mới nhất so với 4 mốc ngay trước đó; xấu đi **≥ `RANK_ALERT_TREND_DROP`** (mặc định 3) vị trí → tin 🌡️ "xu hướng giảm dần, dự báo sẽ rớt" **trước khi** chạm ngưỡng tụt đột ngột. Chuỗi phải đủ 4+4 mốc đo được liên tục — đứt giữa (không vào top N) thì không ước lượng. Tắt bằng `RANK_ALERT_TREND_ENABLE = False`.
- **Báo cáo tuần (C3)**: `python main.py --weekly` gộp SERP + Search Console + AEO thành 1 tin Telegram ≤ 4096 ký tự, **1 lần/tuần** (state `data/weekly_digest.json`); nguồn nào chưa có dữ liệu thì bị bỏ, không nguồn nào chết cả báo cáo; `--force` gửi lại. Gửi hỏng mạng thì tuần chưa đánh dấu — lần chạy kế tự thử lại.
- **Báo cáo buổi sáng (F10d)**: `python main.py --daily-report` gộp 1 tin/ngày nhẹ hơn `--weekly` — **tail 10 dòng xếp hạng** + **tail GSC** + **"Việc hôm nay"** (5 mục kế của content plan, số draft CHỜ DUYỆT chưa push WP, nhắc đặt backlink khi danh sách trống). Khác `--weekly`: **không đánh dấu ngày nào trong state** — chạy 2 lần là gửi 2 tin (chạy tay lúc nào cũng được); `--save` ghi thêm `data/<slug>/daily_<ngày>.md`. Scheduler có sẵn job **`daily`** lúc 07:00 (`--run-job daily`), employ `_guard_daily` không chặn gì — tin tự nói phần nào thiếu dữ liệu.
- **Cảnh báo sớm qua dữ liệu GSC (G-B3)**: sau MỖI lần `--gsc`, bộ này so **impressions từng query giữa 2 snapshot gần nhất** — query mốc trước có ≥ 30 imps (được phơi đáng kể) mà mốc mới **< 50%** hoặc biến mất hẳn (imps 0 = Google ngừng phơi) → tin 📉 **trước** khi hạng SERP thật rớt (site tụt khỏi top 100 thì đây là tín hiệu duy nhất còn lại). Query mốc trước đã dưới 30 imps là noise, query mới xuất hiện là tăng trưởng — không tin. Chống spam: 1 tin/ngày/query (key `gscdrop:<query>`), gửi hỏng tự thử lại lần fetch sau, lỗi bộ cảnh báo không làm chết fetch. Xem chủ động: `python main.py --gsc-alerts`.

---

### 11. Lịch chạy tự động — Windows Task Scheduler (F4)

- **Đồng hồ không nằm trong code.** Windows Task Scheduler gọi `python main.py --run-job rank|gsc|backlink|report|daily|traffic` đúng giờ; `utils/scheduler.py` chỉ quyết định "giờ này có được chạy không", chặn hai job chồng nhau (`data/scheduler.lock` — PID + heartbeat, stale 20 phút) và ghi dấu vết vào `data/scheduler_state.json`. Job **`report`** (P3-3): xuất `data/report.html` gộp từ dữ liệu có sẵn, `SCHEDULER_REPORT_HOURS` rỗng (mặc định) = khớp giờ GSC — GSC kéo xong là report hơi nóng giá.
- **Không tự nới giới hạn.** Job `rank` vẫn bị `RANK_CHECK_MAX_PER_DAY`/`RANK_CHECK_MIN_INTERVAL` chặn, `gsc` vẫn bị `GSC_MAX_FETCH_PER_DAY`, `backlink` chạy đúng engine `--backlink-check` (không fetch thêm, không retry 403/429), `traffic` vẫn bị rate limiter — scheduler gọi lại đúng hàm check của module gốc chứ không đếm riêng.
- **Job `backlink` mặc định không tự chạy** (`SCHEDULER_BACKLINK_HOURS = []`): điền ví dụ `[9]` như `SCHEDULER_GSC_HOURS` và đăng ký task tương tự nếu muốn verify link hàng tuần; danh sách link rỗng thì job tự dừng và nhắc lệnh `--backlink-add`.
- **Traffic mặc định TẮT tự chạy** (`SCHEDULER_TRAFFIC_ENABLE = False`): bật lên là quyết định của bạn, vì chạy lúc không có ai nhìn thì lỗi tích âm thầm.
- **Tin Telegram tóm tắt sau job** (mặc định TẮT, `SCHEDULER_NOTIFY_ENABLE = False`): bật cùng `ALERTS_ENABLE` để nhận 1 tin ngắn sau mỗi job — job gì, xong hay lỗi, exit code; job `rank` xong thì kèm số cảnh báo đang chờ. Tin gửi lỗi không bao giờ làm job tính là thất bại.
- **Không chạy bù**: máy tắt đúng giờ thì mất lượt trong ngày — không gom nhiều lần check một lúc cho đỡ "phí".
- **Chạy nền không ngồi chờ**: job `rank` gặp CAPTCHA thì bỏ qua từ khóa đó (khác với bấm `--rank` trong GUI, có ô hỏi người giải).
- Xem lại: `python main.py --scheduler-status` (job nào chạy lúc nào, exit code, lỗi cuối, 5 lần gần nhất) hoặc khung **🗓 LỊCH TỰ ĐỘNG** trong tab 📈 Xếp Hạng. GUI cố ý **không** có nút chạy job — muốn chạy tay thì dùng CLI để log nằm đúng chỗ.
- **GUI nút 📋 SINH LỆNH SCHEDULER (T21)**: cạnh nút LOAD TRẠNG THÁI trong khung 🗓 LỊCH TỰ ĐỘNG — in các lệnh `schtasks /Create` (`schtasks_commands()`, thuần dữ liệu, không chạy schtasks) vào khung **và COPY sẵn vào clipboard**; paste vào Command Prompt để đăng ký. Jobs giờ rỗng → nhắc chạy tay `--run-job`, không lệnh nào. Cùng ranh giới T20: GUI chỉ HIỆN, không tự đăng ký gì.
- **GUI nút 🪟 TASK ĐÃ ĐĂNG KÝ? (T49)**: cạnh hai nút trên — hỏi Windows thật (`schtasks /Query /TN`, chỉ ĐỌC — không Create/Delete/Change) từng task mà `--scheduler-install` sẽ in, đổ vào khung `✓/✗` + đếm `k/9`; thiếu thì bấm SINH LỆNH để chép lệnh. Đây là mắt xích còn thiếu của bootstrap: LOAD TRẠNG THÁI chỉ đọc kết quả **run** (`scheduler_state.json`), không biết task có tồn tại trong Windows hay không.
- Đăng ký lịch từng bước (4 lệnh `schtasks`): **[`docs/SETUP_SCHEDULER.md`](docs/SETUP_SCHEDULER.md)**.
- **`--scheduler-install` (T20)**: **in sẵn toàn bộ lệnh `schtasks /Create`** theo giờ trong `config/settings.py` (`SCHEDULER_*_HOURS`) — tên task `SEO-Bot-<Job>-<HHMM>`, `/RL LIMITED`, log dồn `data\scheduler.log`. Tool chỉ **IN THÔI, không tự đăng ký** (không gọi schtasks) — bạn copy dán vào Command Prompt; đổi giờ trong settings thì chạy lại lệnh rồi copy. Jobs không có giờ (backlink/traffic mặc định) bị bỏ qua và được nhắc chạy tay `--run-job`.

---

### 12. Audit on-page + Core Web Vitals (F6)

- `python main.py --audit` crawl **chính site trong `TARGET_URL`** (tối đa `AUDIT_MAX_PAGES` trang, `AUDIT_TIMEOUT` giây/trang) bằng **HTML tĩnh qua `requests`** — không mở trình duyệt, không đụng lớp anti-detect, và **không bao giờ** request ra ngoài domain của bạn (kể cả link ngoài hay sitemap trỏ host khác).
- 20 rule on-page, mỗi lỗi in kèm **severity + URL**: thiếu `title` / title dài ngắn bất thường / thiếu `meta description` / meta quá dài / thiếu `H1` / nhiều `H1` / heading nhảy cấp / ảnh thiếu `alt` / `alt=""` hàng loạt / thiếu `canonical` / `canonical` đáng ngờ / `noindex` lạc chỗ / link `http://` nội bộ / thiếu `lang` / **link nội bộ hỏng (404, 410)** / trang không đọc được / `title` trùng giữa các trang / thiếu `sitemap.xml` / URL bị robots chặn.
- **Tôn trọng `robots.txt`** của site mình (tự parse theo quy tắc Google: đường dẫn khớp **dài nhất** thắng — `urllib.robotparser` 3.11 khớp theo thứ tự khai báo nên đã đo và không dùng), ưu tiên URL lấy từ `sitemap.xml`, không có sitemap thì lần theo link nội bộ. Trang 404/5xx/timeout là **một dòng báo cáo**, không làm dừng cả đợt.
- Kết quả lưu vào `data/audit_last.json` → `python main.py --export audit` ra CSV (`severity,rule,url,detail`, UTF-8 BOM) mở bằng Excel. GUI: tab **📈 Xếp Hạng** → nút **🔍 AUDIT SITE** (thread nền, log in ra khung, chạy xong tự xuất CSV).
- `python main.py --pagespeed [URL]`: **LCP / CLS / INP** + điểm hiệu năng, cả mobile lẫn desktop, qua PageSpeed Insights API; chỉ lưu số gọn trong `data/pagespeed.json` (không lưu response thô, vài MB).
- Số PSI là **LAB** (Lighthouse do Google chạy hộ lúc gọi), **không phải field data CrUX**. API **không cần key**, nhưng quota ẩn danh là *"Queries per day" dùng chung toàn cầu* — **đo thật 2026-10-14: đang cạn**, nên lệnh hiện trả thông báo 429 và exit 1. Muốn có số: tạo key miễn phí rồi điền `PAGESPEED_API_KEY` (key là secret của bạn — code không in ra log, không ghi vào file).
- **PageSpeed cho bài vừa push (T33)**: scheduler job `pagespeed` (mặc định 06:00 hằng ngày) tự đo **mới** bài nào trong `wp_pushed.json` chưa có điểm — **1 request/URL trọn đời** (đo xong ghi key vào `pagespeed_posts.json`, lần chạy kế bỏ qua = 0 request), mỗi đợt tối đa `PAGESPEED_MAX_PER_RUN` URL (5 — Lighthouse mất chục giây/URL). Bài lỗi (mất mạng, HTTP lạ) **không ghi state** — lần chạy kế tự thử lại; PSI 429 giữa đợt thì job dừng nguyên đợt (quota cạn, chạy tiếp vô nghĩa). Xem: `--pagespeed-posts` (bảng điểm kém nhất trước, LAB mobile); `--pagespeed-posts "URL"` = **đo lại** một bài (xóa điểm cũ, 1 request mới). Bài điểm < `PAGESPEED_WARN_SCORE` (60) → tối đa 2 dòng nhắc trong `--daily-report` kèm lệnh đo lại. Chỉ đo trang của MÌNH (TARGET_URL / link trong wp_pushed) — key nếu điền là secret, không in log.
- `python main.py --audit-actions` (C2): biến findings của lần audit gần nhất thành **việc ưu tiên theo từ khóa** — URL của lỗi được ghép với từ khóa trong `config/keywords.json` (kỹ thuật so token không dấu, URL phải khớp ≥ 2 token có nghĩa → trang `/blog/p5` hay trang chủ không bao giờ bị gán oan), sắp xếp **CAO trước** rồi in tối đa 5 việc (`--limit N`). Lỗi trang chủ (không khớp từ khóa nào) thành nhóm "Trang chủ/tổng" vì ảnh hưởng mọi từ khóa. Chưa từng chạy `--audit`? Lệnh in ra hướng dẫn chạy `--audit` trước thay vì im lặng.

---

### 13. Backlink auto-check — link bạn đã đặt còn sống không? (F7)

- Danh sách link để check là **`config/backlinks.json`** — tức những chỗ bạn **đã thật sự đặt link** (bài guest post, danh bạ, forum...), không phải `BACKLINK_OPPORTUNITIES` trong `backlinks/tracker.py` (đó là danh sách **cơ hội** `status: "todo"`, verify thì 100% báo "không có link tới site").
- `python main.py --backlink-check` trả lời ba câu cho từng link: trang đích **còn sống** (HTTP 2xx/3xx)? trên trang **có** link tới domain trong `TARGET_URL`? link đó **dofollow** hay `nofollow`/`sponsored`/`ugc` (ba giá trị sau không chuyển uy tín)? Kèm anchor text và số link tìm thấy.
- "Có link" so theo **hostname đã parse**: `nankybeauty.com` và mọi subdomain đều tính, `nankybeauty.com.evil.io` thì không (bẫy `endswith` trên chuỗi). Redirect sang domain khác vẫn được verify trên HTML trả về và ghi lại `url cuối`.
- **Lịch sự với site người khác**: tối đa `BACKLINK_PARALLEL` luồng (5), timeout `BACKLINK_TIMEOUT` giây (15), **một request mỗi URL mỗi lần chạy**, UA desktop tĩnh (`AUDIT_USER_AGENT`). 403/429 → ghi "bị chặn" rồi đi tiếp, **không** retry, **không** đổi UA, **không** giải CAPTCHA — đó là lớp anti-detect đã tuyên bố không đụng tới. 404/410/timeout là **dữ liệu**, không làm dừng cả đợt.
- Kết quả lưu `data/backlink_status.json`; URL đã check trong `BACKLINK_CACHE_HOURS` (24h) được **dùng cache** — chạy lại trong ngày không refetch. `--backlink-refresh` mới check lại hết, `--backlink-limit N` giới hạn N link mỗi đợt.
- `python main.py --export backlinks` ra CSV mở Excel (UTF-8 BOM, dòng có vấn đề xếp trước). GUI: tab **📈 Xếp Hạng** → nút **🔗 CHECK BACKLINK** (thread nền, chạy xong tự xuất CSV và in đường dẫn).
- Thêm link: `--backlink-add "https://blog-nguoi-khac/bai-cua-ban"`, hoặc nạp cả loạt bằng `--backlink-import <file.csv>` đọc từ CSV **"External links"** tải tay trong Search Console (Properties → Links). **API của GSC không có endpoint external links** nên con đường duy nhất là tay export; parser không tin tiêu đề cột (GSC đổi tên cột theo phiên bản) mà nhận ra URL trong **mọi ô**, bỏ trang của chính site mình và URL đã có.
- **Giới hạn**: không đo DA/DR/traffic của trang đặt link (Ahrefs/Moz API trả phí) nên không xếp được "link này tốt hay xấu", không tự tìm backlink mới, không tự đặt link. Chỉ đọc HTML tĩnh — link render bằng JS (widget, iframe lazy) không được đếm. Check link chỉ trả lời "trang đó còn tồn tại và còn link tới site mình không", không chứng minh Google đã index hay tính giá trị link.

### 13b. Sổ outreach — lời đề xuất đặt link (T32)

- **Vòng đời lời xin link**: **proposed** (đã gửi mail/tin nhắn bằng tay) → **agreed** (người ta đồng ý) → **placed** (link đã sống — chạy tiếp `--backlink-add` để hệ verify ở trên lo phần còn sống/dofollow) — hoặc **dead** (mai một). Lệnh: `--outreach-add "URL-bài-người-ta" --outreach-kw "anchor" [--outreach-title] [--outreach-contact] [--outreach-note]`, `--outreach-list`, `--outreach-set URL --outreach-state proposed|agreed|placed|dead`, `--outreach-remove`. Trang đích nên là **bài cụ thể** chứa chỗ đặt link, không phải trang chủ.
- **Chống trùng + mốc thời gian**: một trang = một mục (chuẩn key bỏ tham số tracking của backlink store — `?utm_*`, trailing slash là một); mỗi state tự ghi mốc `proposed_at/agreed_at/placed_at/dead_at`; thêm lại URL đang dead là **mở vòng mới** (mốc đề xuất reset), URL đang placed thì chặn (đã vào danh sách verify rồi). Đi lui được: agreed → proposed.
- **Nhắc đúng chu kỳ, không spam**: `--daily-report` (và scheduler job `daily`) thêm dòng cho bài **proposed ≥ 7 ngày** chưa phản hồi hoặc **agreed ≥ 5 ngày** chưa đặt link (ngưỡng `OUTREACH_REMIND_PROPOSED`/`OUTREACH_REMIND_AGREED`), tối đa 2 dòng/lần; đặt xong / dead / còn tươi không xuất hiện. Sổ đầy đủ trong section "Sổ outreach — xin đặt link" của `--html-report` (table trạng thái + số ngày chờ). **Tool chỉ ghi sổ + nhắc** — tự liên hệ, tự gửi mail, tự crawl site người ta đều KHÔNG làm; hướng dẫn: [docs/USE_OUTREACH.md](docs/USE_OUTREACH.md).

---

### 14. Content generation bằng Ollama — draft bài tiếng Việt (F8)

- Chọn một mục trong content plan 30 ngày → sinh **dàn ý** → viết **bản nháp** markdown tối ưu từ khóa → lưu vào `content/drafts/<slug>-<timestamp>.md`. Model mặc định `qwen3:30b-a3b` (README Ollama), chạy local qua `OLLAMA_URL`, **không** gửi gì ra ngoài máy.
- `python main.py --generate "nối mi tự nhiên"` (hoặc `--generate --day 3` lấy đúng mục ngày 3 trong plan, hay `--generate "kw"` rơi về `config/keywords.json` nếu không truyền). Chạy 2 lần cùng từ khóa → **2 file khác nhau**, không ghi đè.
- `--dry-run` chỉ **in prompt** (outline + draft) mà **không gọi Ollama, không tạo file** — dùng để xem tool sẽ hỏi model gì trước khi tốn thời gian.
- Mỗi bài có **frontmatter** (keyword, topic, type, date, model) và được tự kiểm tra SEO thô in ra console: từ khóa có trong **H1**? xuất hiện mấy lần? có trong **2 đoạn mở đầu**?
- GUI: tab **🤖 AI Engine** → ô từ khóa + nút **✍️ SINH BÀI** (thread nền, đọc Ollama URL ngay trên tab, xong in đường dẫn draft xuống log). **T48 bổ sung**: ô **ngày** + nút **📅 SINH THEO NGÀY PLAN** (sinh đúng mục ngày N của plan 30 ngày — lỗi điền không phải số thì in hướng dẫn, không sinh), nút **📋 DRAFT CHỜ** liệt kê 30 mục plan + trạng thái draft/push vào System Logs (chỉ READ; sinh bài và đẩy WP vẫn qua CLI/duyệt tay — GUI không thêm đường đẩy WP).
- **Tool CHỈ sinh, không tự đăng.** Không có WordPress API, không sinh ảnh, không đăng hàng loạt cả tháng — bạn duyệt và tự dán lên site. Văn phong/độ chính xác của bản nháp là việc bạn kiểm; prompt chỉ là hướng dẫn tiếng Việt, không phải RAG nên không guarantee số liệu đúng.
- Timeout mỗi lượt `CONTENT_GEN_TIMEOUT` (300s — model 30b chậm), `CONTENT_GEN_RETRIES` (1) **chỉ áp dụng khi timeout**, connection error báo ngay không retry.
- **Giới hạn / chưa verify**: trên máy dev Ollama **chưa chạy** (đo 2026-10-14), nên pipeline + ghi file chỉ được chứng minh bằng unit test tiêm client giả — **chưa** có bài thật từ `qwen3:30b-a3b`. Muốn xem chất lượng bài: `ollama serve` + `ollama pull qwen3:30b-a3b` rồi chạy `--generate`. `content/drafts/` được gitignore (dữ liệu nháp, owner duyệt rồi mới dùng).

### 15a. Đẩy bản nháp lên WordPress — chỉ DRAFT, bạn vẫn duyệt (C1)

- `python main.py --wp-push content/drafts/<file>.md`: đọc file nháp F8, **bóc frontmatter** (keyword → title/excerpt/slug), đẩy lên WordPress qua **REST API `/wp-json/wp/v2/posts`** với `--status` trần chốt là **`draft` / `pending`** — `publish` / `future` / `private` bị **từ chối ngay trong validate**; tool không có đường tắt nào đăng thẳng bài. Duyệt bài vẫn là việc của bạn trên WP.
- Chuẩn bị 3 biến trong settings PHẦN L: `WP_URL` (VD `https://nankybeauty.com`, không có `/wp-json`), `WP_USER`, `WP_APP_PASSWORD`. **App Password** tạo trong WP admin (Users → Profile → **Application Passwords**) — đây là mật khẩu riêng cho tool, **không** là mật khẩu đăng nhập, dễ thu hồi; hoặc để ở **biến môi trường `WP_APP_PASSWORD`** (thắng settings.py, không log, không commit).
- Title theo thứ tự: `--title` → frontmatter `title` → H1 đầu trong bài → từ khóa frontmatter. `--excerpt` ghi đè excerpt lấy từ frontmatter. Nội dung gửi dạng **markdown thô** — WP Gutenberg + plugin markdown sẽ render; trên site không có plugin markdown thì nên đẩy trang HTML.
- Cảnh báo nhẹ (không chặn): domain `WP_URL` khác `TARGET_URL` → nhắc "báo cáo xếp hạng của site khác với site nhận bài nháp". Lỗi WP (403 sai App Password, thiếu quyền...) in rõ mã lỗi, không bao giờ crash, App Password không bao giờ in ra log nào.

### 15. Multi-site — nhiều website trong cùng một bộ máy (F10)

- **Ý tưởng**: một project chạy cho nhiều site, mỗi site có dữ liệu riêng (`rank_history`, GSC, keywords, backlink, audit, scheduler...) để chúng không ghi đè nhau. Nhận diện site bằng **domain** lấy từ `cfg.TARGET_URL` (bỏ `www.`, bỏ scheme/path), slug hoá thành tên thư mục (vd `shoplanhdep.com` → `shoplanhdep-com`).
- **Bật per-site = có dấu `data/<slug>/.migrated`** (migrate ghi ở bước cuối, khi đã copy xong). Đây là quyết định duy nhất (QĐ B): khi thiếu dấu đó, mọi đường dẫn rơi về **file phẳng gốc** như cũ → bạn chỉ có 1 site và chưa migrate thì hành vi y hệt hôm nay, không đổ vỡ gì.
- **Di chuyển dữ liệu (không phá)**: `python main.py --migrate-multi-site --dry-run` xem trước sẽ copy gì, rồi `python main.py --migrate-multi-site` chạy thật. Lệnh **chỉ copy**, **không bao giờ xoá/dời file gốc** — bạn tự kiểm tra `data/<slug>/` đọc đúng rồi hãy tự tay dọn file phẳng. `config/gsc_service_account.json` (credential) **cố ý nằm ngoài** danh sách migrate.
- **Chọn site khi chạy CLI**: `python main.py --site domain.com --rank` — `--site` áp dụng trước khi nạp module nên cả phiên đó trỏ đúng site (site phải đã migrate mới có dữ liệu riêng).
- **GUI**: tab **⚙️ Cấu hình** giờ quản sổ site trực tiếp (F10b/F10c): **dropdown sổ site** (url từ `config/sites.json`) + nút **📂 Site sổ** (chọn → điền Target URL + áp dụng như nút 🔀), **➕ Thêm site** (thêm site ở Target URL vào sổ — CLI nhắc migrate nếu chưa tách dữ liệu), và **⚡ Chạy cả sổ** + dropdown lệnh (Check rank / GSC fetch / Audit / Report HTML): chạy **process con mỗi site** như `--sites-run`, bảng tổng hợp ✅/❌ in ra log pane; có job nào đang chạy thì ⚡ từ chối (tránh dữ liệu lẫn site). Cũng sửa 1 lỗi tiềm ẩn: bấm automation khi Target URL vừa đổi giờ áp site **đúng nghĩa** (cập nhật `GSC_SITE_URL`, in thông điệp) **trước khi** lưu từ khóa — nháp từ khóa không rơi vào keywords.json của site sai. Tab **⚙️ Cấu hình** → nhập Target URL rồi bấm **🔀 Áp dụng site**; chuyển `cfg.TARGET_URL` + `GSC_SITE_URL` ngay trong phiên, reload từ khóa, in ra chế độ per-site BẬT/TẮT và danh sách site đã biết. Đang chạy job thì nút từ chối đổi (tránh dữ liệu lẫn lộn giữa chừng).
- **Báo cáo CSV**: multi-site thì tên file có prefix `<slug>_export_...`; đơn site thì không — giữ nguyên như F1.
- **Nhân vật trình duyệt dùng chung (QĐ C)**: F10 chỉ đổi **đường dẫn dữ liệu**, **không** đụng cơ chế fingerprint/persona. Ổ khoá scheduler cũng **dùng chung** (QĐ lock) — hai job đồng thời vẫn chặn nhau đúng như cũ.
- **Sổ site (F10b)**: `config/sites.json` — danh sách site của bạn tại một nhà. `python main.py --sites` in sổ kèm đối chiếu site nào **dữ liệu đã tách riêng** (✓ — có dấu `.migrated`) hay sổ có tên nhưng chưa migrate (✗); `python main.py --site-add "https://web.com" [--label "..."]` thêm site (khử trùng theo domain gấp không dấu, thêm trùng bị từ chối), `--site-remove "https://web.com"` bỏ khỏi **sổ thôi** — dữ liệu `data/<slug>/` không bị xóa theo. Sổ chỉ GHI NHỚ, không tự migrate và không thay đổi cơ chế resolve của F10.
- **Chạy lệnh qua cả sổ (F10c)**: `python main.py --sites-run "--rank"` mở **process con mỗi site** (`python main.py --site <url> --rank`) — đúng luật F10 "một phiên một site", không nhảy cfg giữa phiên. Site nào lỗi thì các site kế tiếp vẫn chạy; cuối bảng tổng hợp ✅/❌ từng site. Nhiều lệnh một phát: `--sites-run "--rank --gsc"`. Timeout mỗi site 30 phút (treo không cản sổ); các lệnh quản sổ/migrate/automation (`--site* --migrate-multi-site --auto --search`) bị từ chối bên trong để không tự lặp vô hạn.
- **Chưa làm / giới hạn**: muốn thêm site mới thì chạy `--migrate-multi-site` cho site đó (tạo tay thư mục `data/<slug>/` **không đủ** — phải có dấu `.migrated` mới bật). Việc migrate dữ liệu thật của bạn là thao tác thủ công có duyệt trước, tool không tự xoá gì.

### 16. AEO tracking — AI có nhắc brand mình không? (F9)

- **Đo AI visibility bằng dán tay**: bạn tự hỏi một AI engine (ChatGPT/Gemini/Perplexity/…) theo từng từ khóa, **copy câu trả lời vào file** rồi chạy `python main.py --aeo-check file.txt --aeo-keyword "nối mi" [--aeo-engine ChatGPT]`. Tool phân tích text đã có — **không gửi request nào ra ngoài, không key, không phí**.
- **Vì sao không tự động hỏi AI bằng browser**: rơi đúng lớp né phát hiện bot mà project tuyên bố không động (giống lý do bỏ F5) — dán tay là phương án đã chốt trong roadmap; phương án API-có-key chỉ thêm khi bạn chốt engine + key (mọi wiring đều xử lý text nên thêm sau không đụng gì).
- **So brand theo từ trọn vẹn + bỏ dấu** (`AEO_BRANDS` trong settings): "nanky beauty" viết không dấu vẫn nhận ra; `nankybeautyva` không bị đếm nhầm là "nanky beauty". Thêm biến thể brand (viết tắt, tên khác, domain) bằng cách thêm vào `AEO_BRANDS`.
- **1 bản ghi/ngày/từ khóa/engine**: dán lại trong cùng ngày là cập nhật, không spam; history lưu tối đa `AEO_HISTORY_KEEP` (500) bản ghi, ghi atomic vào `aeo_history.json` (per-site khi đã migrate).
- **Xem kết quả**: `python main.py --aeo-report` hoặc cột **AI** trong báo cáo gộp (`--gsc-report`) — hiện `✓1/1` (số engine nhắc / số engine đã hỏi). **Chưa dán lần nào → báo cáo gộp y như cũ**, không breaking.
- **Share-of-voice với đối thủ (T23)**: khai **`AEO_COMPETITORS`** trong settings (dict `{tên đối thủ: [biến thể]}`, cùng luật brand mình — bỏ dấu, token trọn vẹn) → khi dán câu trả lời phân tích, tool đếm luôn **đối thủ nào được nhắc trong CÙNG câu trả lời AI** (tính năng chỉ đọc text, 0 request mới). Xem ở mọi nơi: `--aeo-report` in mục SHARE-OF-VOICE (mình được nhắc X/Y câu + từng đối thủ, đếm cả câu nhắc **cả mình và đối thủ**), tab GUI 📢 AI Nói Gì thêm đuôi `so với: Tên×n` mỗi dòng + tổng cuối bảng, `--html-report` thêm bảng đối thủ dưới section AEO. Không khai → tính năng ẩn, chỉ đếm brand mình (báo cáo ở dòng "chưa khai báo"); xóa tên đối thủ khỏi dict → record cũ dán trước đó cũng thôi được đếm.
- **Tab GUI 📢 AI Nói Gì (T17)**: khỏi tạo file answer.txt — hỏi AI, **dán câu trả lời vào khung**, điền từ khóa + engine rồi bấm **PHÂN TÍCH & LƯU**; cùng ngày/từ khóa/engine ghi đè y như CLI. Nút **KIỂM TRA LẠI BẢNG** vẽ matrix từ khóa × engine (engine chưa hỏi ra hàng `—` để nhìn phát biết chỗ trống), nút **IN BÁO CÁO AEO** đổ report đầy đủ vào System Logs. Tool chỉ đọc text — 0 request, chạy thread nền không kẹt cửa sổ, mỗi nút chặn chồng lần chạy trước.
- **Trend AEO theo tuần (T31)**: gộp history theo **tuần ISO** — "tuần này X% câu trả lời AI được nhắc brand". Xem ở 3 chỗ: nút **📈 AEO TREND** trong tab 📢 AI Nói Gì vẽ chart đường vào canvas (dòng tổng + tối đa 3 engine hay xuất hiện; tuần không dán câu nào là **đoạn đứt** — không tính 0% sai nghĩa), section AEO trong `--html-report` thêm 1 dòng trend, báo cáo tuần Telegram (`--weekly`) thêm mục "AEO TREND" mỗi thứ Hai. Dưới 2 tuần có dữ liệu → trend tự ẩn (chưa đủ nói gì); 0 request mới, đọc lại history đã lưu.
- **Trend mini SVG trong section GSC (T42)**: dưới bảng từ khóa, đường **clicks (xanh liền) + hiển thị (xám đứt)** qua **từng lần fetch GSC** — xem tiến/lùi theo thời gian không cần mở GUI chart. SVG tự chứa (không JS, không asset ngoài, điểm tròn đánh vị trí từng mốc, nhãn ngày đầu/cuối + max), **< 2 mốc fetch → tự ẩn**; 0 request mới — chỉ đọc lại snapshot đã lưu trong `gsc_history.json`. Phần điểm `points` chỉ gồm số — nhãn ngày đã qua `html.escape`, an toàn injection.
- **Chuyển động domain đối thủ (T43)**: `--competitors` và section Competitors trong `--html-report` thêm so sánh **mốc đầu → mốc mới nhất** theo từng domain (xuất hiện top-10): từng dòng `(mốc_đầu → mốc_mới (+delta))`, sort theo delta giảm dần — domain đối thủ đang leo lên đứng đầu, thấy ngay ai đang catch up. `< 2 mốc` → khối/cột tự ẩn. Cùng nguồn `top_urls` trong `rank history` đã lưu sẵn — 0 request mới.
- Hướng dẫn từng bước: **[`docs/USE_AEO.md`](docs/USE_AEO.md)**.

---

### 17. `--doctor` — kiểm tra môi trường một lệnh (combo #1); `--setup-wizard` — wizard lần đầu

- `python main.py --doctor` quét nhanh mọi thứ setup xong chưa: site/từ khóa, lịch rank, dữ liệu GSC, Telegram, Ollama (thêm `--net` để gọi thật), backlink, WordPress, bản nháp, thư mục state — mỗi mục trả ✓ sẵn sàng / ! cần lưu ý / ✗ thiếu, kèm hướng dẫn sửa; cuối bảng là dòng tổng và con trỏ tới **[`docs/CHECKLIST_FIRST_RUN.md`](docs/CHECKLIST_FIRST_RUN.md)**.
- **3 mục mới cho lộ trình kích hoạt (T39)**: ① *Job tự chạy (scheduler)* — query `schtasks /Query /TN SEO-Bot-<Job>-<HHMM>` cho **mọi task mà `--scheduler-install` sẽ in** (hiện 9: rank 3 giờ/gsc/report/daily/weekly/airobots/pagespeed), đủ → `✓ 9/9`, thiếu → liệt kê task thiếu + chỉ chạy lại `--scheduler-install`, chỉ ĐỌC không tự đăng ký; ② *IndexNow* — state `indexnow_state.json` chưa có ngày "sent" nào → nhắc `--indexnow-key` + upload key file; ③ *PageSpeed* — chưa điền `PAGESPEED_API_KEY` → nhắc tạo key (tùy chọn — không key PSI vẫn chạy bằng quota ẩn toàn cầu đang cạn, đo 2026-10-14 dính 429). Bảng `--doctor` giờ đủ phục vụ bootstrap từ 0 → chạy theo ✓/! từ trên xuống là ra.
- `python main.py --setup-wizard` (T14): **wizard "bật nhà mới"** — 6 bước theo thứ tự (site & từ khóa → check rank lần đầu → Search Console → Ollama → Telegram tùy chọn → WordPress tùy chọn), mỗi bước chỉ báo xong/thiếu kèm lệnh hoặc docs cần làm; **chỉ đọc file/config, 0 request, không cấu hình gì thay owner**. Bước tùy chọn không chặn tổng thể. GUI cũng có tab **🧙 Cài Đặt Lần Đầu** (nút kiểm tra lại + nút mở checklist docs). Secret (token WP/Telegram) chỉ hiện 4 ký tự cuối.
- `python main.py --first-run` (T15): **chạy thử tuần tự lần đầu** — wizard trạng thái → doctor môi trường → **audit crawl thật site mình** (tối đa 100 trang HTML tĩnh) → xuất CSV các nguồn có (rỗng vẫn chạy, file chỉ có tiêu đề); mỗi bước tự nuốt lỗi riêng, output dài bị cắt với ghi chú "chạy lệnh riêng để xem đầy đủ"; cuối bảng tổng kết [✓]/[✗] mỗi bước + **VIỆC KẾ TIẾP** rút từ wizard steps (bắt buộc trước, tùy chọn kèm nhãn). KHÔNG check GSC thật (403 ở lần đầu là chắn — việc đó thuộc SETUP_GSC.md), KHÔNG mở browser, KHÔNG tự sửa config; exit 0 luôn. GUI cũng có nút **🌱 FIRST RUN** trong tab 🧙 (thread nền, chặn chồng crawl với bot/audit đang chạy).
- **Không bao giờ crash**: mỗi mục tự nuốt lỗi của nó → vấn đề nào có câu trả lời, vấn đề nào không → ra `!`. Secret (Telegram token) chỉ hiện 4 ký tự cuối. Thoát code luôn 0 — đây là lệnh đọc, không phải lệnh chặn.

---

### 17b. Job `weekly` trong scheduler — báo cáo tuần tự động 1 lần/tuần (T16)

- Scheduler thêm job **`weekly`**: mỗi ngày 09:00 chạy `python main.py --run-job weekly` (giờ thật vẫn do Windows Task Scheduler quyết định), job gọi `run_weekly_cli(force=False)` — build digest gộp rank/GSC/AEO rồi gửi qua kênh alerts (1 tin Telegram, hay console khi ALERTS_ENABLE=False).
- **Chống gửi lặp nằm ở `utils/weekly_digest.py`, không ở guard**: state `data/weekly_digest.json` ghi tuần ISO đã gửi; đánh dấu CHỈ KHI send thành công — hỏng mạng thì tuần này chưa đánh dấu, lần chạy kế thử lại. Job chạy mấy lần trong ngày cũng chỉ in nhắc "đã gửi rồi" rồi thoát 0. Guard để trống (luôn mở) vì vậy.
- Mặc định 0 config cần đổi: `SCHEDULER_*` thêm gì thì settings, job chạy theo mặc định. Đăng ký như các job khác trong **[`docs/SETUP_SCHEDULER.md`](docs/SETUP_SCHEDULER.md)**; gửi ngay thử: `python main.py --weekly` (hoặc `--weekly --force` để gửi lại bất chấp state).

---

### 18. Báo cáo HTML 1-file + bộ phân tích từ rank history (P1/P2)

Một cụm tính năng cùng nguyên tắc: **đọc lại dữ liệu đã có** (rank history, audit, backlink status, GSC snapshot) — không thêm request nào, không thêm dependency nào.

- **`--html-report` (P1-1)**: gộp Xếp hạng + Search Console + Audit + Backlink thành **1 file HTML tự chứa** (`data/report.html`, per-site khi đã migrate) — không JS, không asset ngoài, mọi giá trị render qua `html.escape` (dữ liệu GSC/audit là text của bên thứ ba). Nguồn nào chưa có dữ liệu → section gợi ý lệnh cần chạy; nguồn nào lỗi không làm report chết. Ghi **atomic** (tmp + `os.replace`).
- **Section "Tóm tắt — tình hình nhanh" (T34)**: **8 dòng đầu report** — mỗi mảng 1 dòng ghép từ nguồn có sẵn (0 request mới): SERP (bao nhiêu kw top-10, tốt nhất #n), GSC 28 ngày (clicks/imps + Δ so kỳ trước), AEO (% được nhắc tuần này vs tuần trước), hiệu quả bài viết (T30: đang kéo/lẻo/chưa có GSC/draft), outreach (T32: bao nhiêu chờ phản hồi/chờ đặt), PageSpeed (T33: đã đo bao nhiêu, bao nhiêu dưới ngưỡng), backlink (sống/tổng), bot AI (bị chặn/tổng). Nguồn nào chưa có số → hiện "—" xám thay vì ẩn dòng — bảng luôn đủ 8 dòng để nhìn 30 giây nắm cả tình hình; số chi tiết vẫn ở section tương ứng bên dưới.
- **Trang nào đang gánh traffic (T35)**: section Search Console của `--html-report` thêm 1 bảng nhỏ dưới bảng từ khóa — **URL nào đang được Google phơi + được bấm** (từ pages snapshot G-1, gộp biến thể trailing slash và query trùng trang, path hiển thị gọn không URL nguyên si): Clicks/Hiển thị/CTR từng trang, tối đa 8 hàng xếp clicks giảm, dư thì ghi "…và N trang nữa". Snapshot cũ chưa có field `pages` (fetch trước khi có tính năng G-1) → bảng tự ẩn, không nói dối "0 trang"; chạy `--gsc` lấy dữ liệu mới là có. 0 request mới — đọc lại snapshot đã lưu.
- **Cảnh báo "phơi mà chưa ai bấm" (T38)**: ngay trong bảng trang trên, trang nào có **≥ 20 hiển thị mà 0 clicks** gắn nhãn cam "phơi N chưa ai bấm" ngay cạnh path, và dưới bảng nhắc 1 dòng: review **title + meta description** của trang đó — phơi mà không ai bấm là CTR thấp, title/mô tả chưa hấp dẫn thì sửa chữ là clicks lên, không cần đợi viết thêm bài. Ngưỡng 20 imps là để tránh nhiễu; trang imps ít thì chưa đủ ý nghĩa thống kê.
- **Chuyển động domain đối thủ (T43)**: `--competitors` và section Competitors trong `--html-report` thêm so sánh **mốc đầu → mốc mới nhất** theo từng domain (xuất hiện top-10): từng dòng `(mốc_đầu → mốc_mới (+delta))`, sort theo delta giảm dần — domain đối thủ đang leo lên đứng đầu, thấy ngay ai đang catch up. `< 2 mốc` → khối/cột tự ẩn. Cùng nguồn `top_urls` trong `rank history` đã lưu sẵn — 0 request mới.
- **Việc nên làm trước (T36)**: section thứ 2 của `--html-report`, ngay sau Tóm tắt — gộp **việc gấp từ 5 nguồn có sẵn** xếp theo sức nặng (tối đa 8 hàng, mỗi hàng kèm lệnh cụ thể nhưng tool tự chạy — bạn quyết chạy hay không): ① lỗi audit mức CAO (tối đa 3) → `--audit-actions`; ② link backlink đã đặt đang chết/chuyển hướng/bị chặn (tối đa 2) → `--backlink-check`; ③ bài lẻo hoặc phơi không ai bấm (T30, tối đa 2) → `--post-report`; ④ outreach quá hạn chờ phản hồi/đã đồng ý mà chưa đặt (T32, reminder như báo cáo ngày) → `--outreach-list`; ⑤ bài PageSpeed dưới ngưỡng (T33) → `--pagespeed-posts`. CAO màu đỏ lên trước, rồi nặng/chờ. 5 nguồn đều trống → một dòng "không có việc gấp" xám — không giấu section, không nói dối. 0 request mới — chỉ đọc lại state đã lưu.
- **Việc gấp vào báo cáo ngày/tuần (T37)**: cùng **một bộ gom** của T36 (module `utils/actions.py`) xuất hiện ở `--daily-report` (tối đa 4 dòng CAO/backlink/bài lẻo — outreach + PageSpeed đã có dòng riêng từ T32/T33 nên không nhắc kép) và `--weekly` (section "VIỆC ƯU TIÊN", tối đa 3 dòng). Format `[CAO] việc (path trang) — lệnh`, xếp CAO trước, 0 request mới — đọc lại các state đã lưu.
- **Trend audit + đối thủ vào báo cáo tuần (T44)**: `--weekly` thêm 2 section — **TREND AUDIT** (1 dòng "Tổng lỗi A → B qua N lần audit (↓ tốt/↑ xấu/không đổi)" từ dữ liệu T41) và **ĐỐI THỦ ĐANG LEO** (tối đa 3 domain đang **tăng** số lần xuất hiện top-10, format `dom 2→4 (+2)`, từ dữ liệu T43; không có mover nào thì ẩn). Cả hai đều chỉ đọc history đã lưu — 0 request mới; thiếu dữ liệu thì section tự bỏ, không chết digest.
- **`--internal-links`** (P1-2): gợi ý link nội bộ — mỗi từ khóa ghép với các trang site của mình (URL lấy từ audit + rank history), khớp ≥ 2 token có nghĩa (cùng kỹ thuật so không dấu của `--audit-actions`), xếp theo số token khớp. Tool chỉ IN gợi ý — bạn tự chèn link trong bài.
- **`--competitors`** (P2-1): đếm tần suất **domain đối thủ** trong top URLs mà rank tracker đã lưu (từ lần `--rank` sau khi có tính năng; các lần cũ chưa lưu top URLs bị bỏ qua, không migrate). Tự loại domain của mình khỏi bảng; cần ≥ 2 lần check mới có số.
- **`--keyword-groups`** (P2-2): nhóm từ khóa **trùng ≥ 2 token** thành cụm (mỗi từ khóa thuộc đúng 1 cụm — thứ tự nhập thắng), kèm **danh sách bài nên refresh**: hạng hiện tại trong vùng 5–15 và từng vào Top 10 trước đây, xếp theo tiềm năng (đỉnh cũ − hiện tại). Dữ liệu từ rank history, không gọi mạng. **Hiệu năng theo cụm** (P3-2): section thứ ba đếm từng cụm có bao nhiêu member đang Top 10, hạng trung bình và xu hướng (+/−) so với mốc trước — cụm nào mạnh cụm nào kẹt nhìn một phát.
- **`--cluster-gsc`** (G-C1): cùng cụm P2-2 nhưng ghép với **dữ liệu Google thật** (snapshot GSC 28 ngày mới nhất — 0 request mới): mỗi cụm được chấm imps/clicks **tổng các member GSC biết**, CTR và vị trí **trung bình**; ba nhóm tách riêng — **của Google đang phơi** (có imps), **cụm mù GSC** (toàn member 0 imps — cụm mới viết/chưa index là bình thường, cụm cũ vẫn mù là gợi ý xem lại identity bài viết), và **từ khóa đơn độc** (không đủ 2 token chung). SERP chỉ nhìn được từ khóa lọt Top 100; cụm 0 imps là tín hiệu sớm trước khi có hạng nào để đo.
- **`--rank-urls`** (P3-1): trang nào đang xếp hạng cho từ khóa nào — rank tracker từ bản P2-1 lưu **top 10 URL** mỗi từ khóa mỗi lần check, lệnh này đọc lại (không request mới): bảng kw → trang đang rank (path), gắn cờ **"đa trang SERP"** khi > 1 trang cùng site nằm trong Top 10, và **cảnh báo "đổi trang rank"** khi 2 lần check gần nhất rank bằng URL khác nhau (dấu hiệu Google chưa chốt trang "chính" — xem `--internal-links` hoặc hợp nhất nội dung). Các mốc cũ không có top_urls bị bỏ qua, không migrate.
- **`--aeo-questions "kw"`** (P2-3): sinh **biến thể câu hỏi AEO** theo angle — `best` (kinh điển), `compare` (có kình địch), `how` (thông tin), `local` (vùng địa danh), `url` (đòi URL site) — `--aeo-angle best,compare` để chọn nhóm khác. Tool chỉ PHÁT câu, bạn dán tay vào engine như F9.
- **`--ai-robots`** (T22): **bot AI nào bị robots.txt chặn?** — AEO phụ thuộc engine đọc được site; quản trị viên chặn bot AI (GPTBot, PerplexityBot...) là quyết định hợp lệ nhưng site mình chặn thì AI phải dựa dữ liệu bên thứ ba. Lệnh fetch robots.txt **1 request duy nhất**, đối chiếu 12 bot đã biết (GPTBot/OAI-SearchBot/ChatGPT-User/ClaudeBot/Claude-Web/anthropic-ai/PerplexityBot/Google-Extended/CCBot/Bytespider/FacebookBot/Amazonbot) mỗi con một trạng thái — **⛔ CHẶN toàn site / ⚠️ KHAI BÁO 1 phần / 🌫️ rơi nhóm `*` / ✅ trống**, kèm Disallow cụ thể và nhận xét bot nào ảnh hưởng AEO nhất (OAI-SearchBot, PerplexityBot). Parse tái dùng `_parse_robots` của audit (khớp dài nhất thắng). **Tool chỉ báo cáo — KHÔNG tự sửa robots.txt**; sửa là tay trên site, quyết định của owner. GUI: nút **🤖 BOT AI BỊ CHẶN?** trong tab 📢 AI Nói Gì (fetch ở thread nền, kết quả đổ vào matrix textbox); kết quả mỗi lần chạy được lưu `ai_robots_last.json` → section "Bot AI" trong `--html-report` (T25) đọc lại, 0 request; **scheduler job `airobots` (T26)** tự chạy 1 lần/tuần thứ Hai 07:00 (đăng ký task qua `--scheduler-install`) để section luôn tươi. **Phát hiện robots.txt thay đổi (T28)**: mỗi lần chạy CLI/scheduler còn ghi 1 mốc vào `ai_robots_history.json` (tối đa 30 mốc ≈ 7 tháng) và so với mốc gần nhất trước đó — bot nào **CHẶN ↔ bỏ chặn ↔ thêm chặn 1 phần** được in thẳng ra sau bảng + dòng ⚠️ trong section Bot AI của report.html ("Thay đổi so lần check trước: GPTBot: không nêu → CHẶN (/)"); robots ổn định → không in gì (không spam); lịch hỏng/mốc thiếu bots tự bỏ. Nút GUI hiện drift để xem nhưng KHÔNG ghi mốc — mốc chỉ ghi qua CLI/job schedule (bấm nút vô hạn không làm history dồn mới).
- **GUI**: tab **📈 Xếp Hạng** có thêm hàng nút **🌐 XUẤT REPORT HTML / 🧩 GỢI Ý LINK NỘI BỘ / 📝 VIỆC ƯU TIÊN TỪ AUDIT / 🩺 DOCTOR / 📋 PLAN PROGRESS / 📉 GSC ALERTS / ⚖️ CỤM × GSC / 📊 GSC TREND / 🎯 CTR OPS** — cùng cơ chế thread nền với các nút cũ (Nút PLAN chạy `--plan-progress` chỉ đọc; nút GSC ALERTS chạy `--gsc-alerts`, chạy qua cùng kênh Telegram/console của bộ cảnh báo; nút CỤM × GSC chạy `--cluster-gsc`; nút GSC TREND chạy `--gsc-trend`; nút CTR OPS chạy `--ctr-ops`).
- **GUI tab 🧰 Phân Tích (F10i, T40)**: 8 lệnh phân tích có mặt sạch riêng, khỏi thêm nút vào tab Xếp Hạng đã chật — **🩺 DOCTOR --net / ⚖️ PAGE IMPACT / 🕳️ CONTENT GAP / 🔁 REFRESH DIFF / 📰 CONTENT BRIEF (có ô nhập từ khóa, `--save` luôn) / 🌅 DAILY REPORT / 📄 POST REPORT / 📣 SỔ OUTREACH** — hai nút mới chạy chính lệnh T30/T32 (đọc sổ — không thêm/sửa nội dung gì từ GUI). Cùng mô hình thread nền (guard tag riêng → disable → thread → finally enable); kết quả in vào **System Logs** bên dưới. `utils/dispatch_tools.py` là nơi duy nhất map tag → lệnh — chỉ chứa lệnh đọc, không có lệnh ghi state. Nút **🌐 XUẤT REPORT HTML** (tab Xếp Hạng) giờ **tự mở report trong browser mặc định** sau khi xuất xong — bấm là thấy, khỏi tìm file; nếu browser không mở được vẫn in đường dẫn để double-click.
- **GUI nút 📈 CHART (F10k)**: nút trong tab Xếp Hạng vẽ **đường hạng thật** vào canvas (tkinter thuần — 0 dependency mới), toggle hiện/ẩn với textbox. Đường được vẽ cho tối đa 5 từ khóa đang có hạng, 8 mốc gần nhất, **trục đảo: hạng 1 ở trên** — đi lên nghĩa là tốt. Canvas ẩn/mở không che mất báo cáo chữ; `utils/gui_charts.py` để hình thuần (`chart_items`, `rank_series_from_history`) riêng khỏi vẽ — test khẳng được hình mà không cần GUI.
- **GUI tab 🧙 Cài Đặt Lần Đầu (T14)**: wizard 6 bước bật nhà cho owner mới — bước nào ✓ xong, ✗ thiếu (kèm lệnh/docs để làm), bước tùy chọn Telegram/WordPress đánh `—`. **Chỉ đọc file/config — 0 request, không tự cấu hình gì thay owner**; dòng tổng "X/4 bước bắt buộc — nên làm trước: ..." ở trên bảng. Nút **🧙 KIỂM TRA LẠI** (thread nền, không chặn UI) và **📖 MỞ CHECKLIST DOCS** (`os.startfile` docs/CHECKLIST_FIRST_RUN.md). Secret (token Telegram/Pass WP) chỉ hiện 4 ký tự cuối — không bao giờ in nguyên.
- **AEO section trong report (T19)**: `--html-report` giờ có mục **"AEO — AI trả lời có nhắc brand?"** — bảng từ khóa × engine (ChatGPT/Gemini/...) với ✓/✗ nhắc brand, số lần nhắc, ngày hỏi gần nhất; đọc `ai_matrix()` từ `aeo_history.json` (0 request mới). Chưa hỏi câu nào → section in hướng dẫn `--aeo-check` + docs/USE_AEO.md. (Cột "AI" nhỏ của section GSC giữ nguyên.)
- **Bot AI section trong report (T25)**: `--html-report` thêm mục **"Bot AI có vào được site? (robots.txt)"** cuối cùng — bảng 12 bot AI kèm trạng thái (CHẶN đỏ / Cho phép xanh / Mặc định xám) + Disallow cụ thể nếu bị chặn; **0 request** — đọc lại file state `ai_robots_last.json` mà `--ai-robots` (T22) lừa lưu mỗi lần chạy. Chưa chạy `--ai-robots` lần nào → section in hướng dẫn. Đầu báo cáo vẫn nhắc ngay: **tool chỉ báo cáo — KHÔNG tự sửa robots.txt**.
- **Domain đối thủ section trong report (T27)**: mục **"Domain đối thủ thường xuất hiện (SERP top-10)"** — cùng nguồn `--competitors` (P2-1): đếm tần suất domain lạ xuất hiện trong `top_urls` của rank history (0 request), loại Google/YT/ads/domains site mình; hiển thị 10 domain xuất hiện nhiều nhất + cột "xuất hiện nhiều ở từ khóa nào" (top 3 từ khóa của domain đó). Đều CHẲNG khẳng định ai "chiếm hạng" — chỉ tần suất xuất hiện; máy check rank toàn CAPTCHA (chưa mốc top_urls nào) → section hint chạy `--rank`. Job scheduler (T26) chạy `--run-job rank` đều đặn thì section tự đầy.
- **`--wp-push` kèm category/tag mặc định** (P2-4): điền `WP_DEFAULT_CATEGORIES` / `WP_DEFAULT_TAGS` (TÊN, owner tự chọn) trong settings PHẦN L — mỗi lần `--wp-push`, tên được tra id qua REST (`GET /wp-json/wp/v2/categories|tags?search=...`), khớp tên chính xác (bỏ hoa/thường) → gán vào payload; term **chưa có trên WP bị bỏ qua + cảnh báo**, **KHÔNG tự tạo term**, bài vẫn đẩy. `[]` = không gán. Frontmatter không nặn term — defaults là quyết định của owner.

---

### 19. Bộ G — phân tích thêm từ dữ liệu đã có (P3 tiếp theo)

Ba tính năng cùng nguyên tắc bộ 18: đọc lại dữ liệu đã có, 0 request mới, 0 dependency mới.

- **`--ctr-ops`** (G-1): query **được Google cho thấy mà ít người click** — đọc snapshot GSC gần nhất, giữ query đang hạng 1..11 (thấy trên SERP, kể cả lẻo trang 2), đủ ≥ `CTR_MIN_IMPRESSIONS` (30) impressions, và CTR thua **CTR bình quân của chính nhóm query đó** (baseline trong-band — CTR tự nhiên giảm theo hạng, so query hạng 5 với hạng 20 là làm sai mốc). Bảng kèm hạng/imps/clicks/CTR/TB/chênh → việc làm: viết lại title/meta description trang tương ứng (lợi ích rõ, từ khóa chính lên đầu). Chưa từng `--gsc`? Tool gợi ý lệnh thay vì im lặng. Thông tin này **rank tracker không đo được** — chỉ Google thật có.
- **Section CTR cơ hội trong report.html (T46)**: engine G-1 (cùng `build_opportunities`, 0 request mới) giờ có bảng riêng trong `--html-report` — sau Search Console: **Query / Hạng / Hiển thị / Clicks / CTR / TB nhóm / Chênh**, chênh ≥ 1 điểm phần trăm màu đỏ, tối đa 8 query (hiển thị imps giảm). Ranking chưa thua bình quân nào → nhận xét "đang đón khách tốt" thay vì bảng rỗng; chưa từng `--gsc` → hint như mọi section khác. Report nay **12 section**.
- **Cảnh báo mất backlink** (G-2): sau MỖI lần `--backlink-check`, engine so state vừa ghi với lần trước; link trước đó "sống + có link + dofollow" mà lần này **trang chết (404/410/5xx) / không đọc được / mất link / chuyển nofollow** → 1 tin qua máy gửi của alerts (Telegram khi `ALERTS_ENABLE`, console khi không). Chống spam dùng chung state 1 tin/ngày (key `backlink:<key>`); **url owner tự gỡ khỏi danh sách không phải "mất"** — không có tin; **lần đầu check không có tin** (chưa có gì để "mất"). Hook tự nuốt lỗi — check backlink không chết theo bộ cảnh báo.
- **`--audit-diff`** (G-3): mỗi lần `--audit` giờ chụp thêm mốc vào `data/audit_history.json` (giữ 20 mốc, cùng nhà với `audit_last.json`, atomic; history hỏng không làm chết audit). Lệnh so 2 mốc gần nhất, khớp theo **(rule, url)** — detail đổi chữ vẫn là cùng lỗi: in ✅ **ĐÃ SỬA** (lần trước có, lần này mất) và ❌ **MỚI PHÁT HIỆN** (lần này xuất hiện); còn 1 mốc thì nói rõ "chưa so được" thay vì fake "0 thay đổi". Biết mình đang tiến bộ hay chểnh mảng, một phát.
- **`--audit-trend`** (T41): **trend theo thời gian** — đếm theo **loại lỗi** xuyên **mọi mốc** trong history (khác diff chỉ so 2 mốc, khớp theo lỗi đơn lẻ): bảng "loại lỗi | mốc đầu → hiện tại (đỉnh) | chuỗi 8 mốc gần | ↓/↑", xếp theo số đếm hiện tại giảm; dòng tổng "201 → 184 ↓" cho biết việc sửa có công hiệu không. Rule mới xuất hiện giữa chuỗi có cửa **0 trước đó** (không gán "lỗi oan" cho lần audit cũ), rule lại biến mất cũng 0 — chuỗi đủ dài bằng số mốc. Cùng nhìn trong section Audit của `--html-report` (bảng dưới findings, arrow ↓ xanh / ↑ đỏ); ≤ 1 mốc → lệnh tự nói "chưa vẽ được trend". 0 request mới — chỉ đọc history đã lưu.
- **`--gsc-pages`** (G-B1): cannibalization theo **dữ liệu Google thật** — mỗi lần `--gsc` fetch thêm một chiều `dimensions=["query","page"]` (cùng lần chạy, rate limit vẫn đếm 1 fetch; lỗi chiều này không chặn snapshot query). Lệnh đọc lại: bảng **query được ≥ 2 trang cùng site phục vụ** (tổng ≥ `CANNIB_MIN_IMPS` 30 imps — trang ít imps vẫn bị nhắc vì Google đang "thử" nó), và phía ngược **trang gánh nhiều query nhất** (≥ 2 query). Khác `--rank-urls` ở chỗ: đây là Google TỰ nói trang nào được hiển thị, không suy từ top_urls. Snapshot cũ không có field `pages` → mục này gợi ý chạy `--gsc` thay vì migrate.
- **`--page-impact`** (F10e): bức tranh **sức nặng theo trang** từ cùng field `pages` của snapshot GSC cuối (0 request mới) — trang nào giữ bao nhiêu % imps toàn site. Ba tín hiệu: **👑 trang VIP** (một trang gánh ≥ `VIP_IMPS_RATIO` 60% imps và ≥ 100 imps — site phụ thuộc 1 trang, rớt là mất nền imps, cần đa nền); **PHƠI MÀ KHÔNG AI CLICK** (CTR < `CTR_NEAR_ZERO` 1% với imps ≥ `CTR_MIN_IMPS` 100 — phơi đủ mà không ai click, title/description chưa chạm người tìm; dưới mốc imps CTR không đáng tin nên chưa bị dính danh); và bảng đầy đủ imps/clicks/CTR/%/số-query của từng trang (tối đa `LOAD_LIMIT` 15 dòng, xếp imps giảm dần). Chỉ READ — chia ngân sách ra sao là quyết định của owner.
- **`--content-gap`** (F10f): mặt ngược của `--page-impact` — **Google muốn, site CHƯA có**. Đọc cùng field `pages` của snapshot GSC cuối (0 request mới): query nào đủ imps (`GAP_MIN_IMPS` 10) mà Google chỉ định **trang chủ** trả lời là site chưa có bài riêng cho query đó — Google đang mượn trang chủ "chống" phần này. Bảng query/imps/clicks (tối đa `GAP_LIST_LIMIT` 15, xếp imps giảm dần) + gợi ý việc (`--generate --day N` / tự viết draft rồi `--wp-push`). Chỉ READ — không sinh bài, không đụng content plan.
- **`--refresh-diff`** (F10g): bước kế của danh sách refresh trong `--keyword-groups` — **bài nên refresh đã xong đến bước nào**. Ghép từng kw "từng top-10, đang tụt 5..15" với trạng thái thực tế: **✍️ CHƯA CÓ DRAFT** (content/drafts/ không có file khớp — viết lại bài), **⏳ CÓ DRAFT CHỜ DUYỆT** (đọc + `--wp-push`), **👀 ĐÃ PUSH WP** (theo dõi 2 lần rank kế — push rồi vẫn tụt là vấn đề cấu trúc bài, mức nặng hơn). Xếp việc gấp trước (chưa làm > chờ duyệt > đã làm), 0 request, chỉ READ.
- **`--content-brief "kw"`** (F10h): **brief trộn dữ liệu** cho 1 từ khóa — nguyên liệu viết bài gộp một cột, KHÔNG gọi Ollama, KHÔNG sinh bài (khác `--generate` là gọi Ollama ra draft). Ghép 4 nguồn (tất cả 0 request mới): **cụm từ khóa** (kw thuộc cụm nào, member là góc phụ — build_clusters), **SERP hiện tại** (hạng + URL lần check gần nhất), **GSC 28 ngày** (row trực tiếp của kw + query liên quan chứa token của kw, tối đa 8 — làm câu hỏi phụ/góc bài), **content plan** (kw thuộc ngày nào → `--generate --day N`). `--save` ghi `data/<slug>/brief_<kw-slug>.md` (atomic). Chỉ READ — dàn ý viết ra sao là quyết định của writer.
- **`--va-pack`** (F10j): **gói việc ngày cho trợ lý** — sinh một file markdown `data/<slug>/va_pack_<ngày>.md` checklist trông thuê: mục plan còn trống kèm lệnh (`--generate --day N`), draft chờ duyệt (`--wp-push`), bài nên refresh đã đến bước nào (✍️/⏳/👀), query gap Google muốn mà site chưa có, query CTR cơ hội cần sửa title/meta, backlink còn sống hay chưa check (checkbox `- [x]` để VA tự bấm). Khác daily-report: **file cho người** (liệt kê đủ, không cắt tail 5), không gửi Telegram; nguồn trống mục đó ghi "(chưa có dữ liệu)" không chết cả gói.
- **`--yoast-meta <post_id> --kw "..."`** (F10l): **write-back Yoast sau `--wp-push`** — REST push không điền được ô của SEO plugin, lệnh này đi SAU khi push: dò Yoast trên post (meta `_yoast_wpseo_*` hoặc `yoast_head_json`), thấy thì PATCH `_yoast_wpseo_focuskw` + `_yoast_wpseo_metadesc` (≤156 ký tự) + `_yoast_wpseo_title` (chỉ khi fold tiếng Việt cho thấy keyword CHƯA nằm trong title, cap 60); không dò thấy Yoast thì fallback PATCH excerpt (core WP) + nhắc owner tự điền. **Chỉ draft/pending** — post đã publish là quyết định của owner, bị từ chối. Descriptions là ĐỀ XUẤT từ dàn ý, owner vẫn sửa trên WP; WP App Password đọc từ env (ưu tiên) / settings, không in ra log.
- **`--gsc-trend`** (G-B2): xu hướng **impressions/clicks/CTR/vị trí theo từng query** qua 8 snapshot GSC gần nhất (0 request mới) — sparkline vẽ lại của rank tracker nhưng cột cao = imps **nhiều** (hữu ích ngược chiều hạng). Query vắng ở mốc nào thì imps 0 mốc đó (Google ngừng phơi — số thật, khác "không có dữ liệu"); CTR/vị trí vắng là `·`. Cờ **⬇️** khi imps mốc mới < 50% mốc trước: **tín hiệu sớm** — site tụt khỏi top 100 thì rank tracker không còn gì để so, đây là tín hiệu duy nhất còn lại. Tracked khớp theo fold dấu tiếng Việt ("noi mi quan 2" = "Nối Mi Quận 2").
- **`--plan-progress`** (F-C1): bảng 30 mục content plan — mục nào **đã có draft** (✓, khớp frontmatter `keyword` của file .md trong `content/drafts/`, fold không dấu như kỹ thuật GSC), mục nào **đã push WP** (✓✓, đọc `data/wp_pushed.json` — `--wp-push` thành công tự ghi keyword + post id vào đây). 0 request, 0 mạng: chỉ map dữ liệu đã có. Cuối bảng gợi ý mục kế tiếp còn trống (`--generate --day N`) và số draft chờ duyệt (`--wp-push`). Chỉ READ — không sinh, không đẩy, tuyệt đối không tự publish.
- **Section kế hoạch 30 ngày trong report.html (T47)**: cùng nguồn `build_progress` — bảng **Ngày / Loại / Từ khóa / Trạng thái** (✓✓ xanh = đã push WP, ✓ cam = draft chờ duyệt, xám = chưa có), dòng đếm `Draft X/30 · đã push WP Y` lên đầu, cuối bảng gợi ý mục kế tiếp còn trống kèm lệnh `--generate --day N`. Report nay **13 section**; bài push ngoài plan không đếm nhầm vào đây (khớp keyword theo plan).
- **`--post-report`** (T30): **bài nào đang kéo, bài nào điêu** — mỗi bài trong `wp_pushed.json` 1 dòng: **Clicks/Impr** từ GSC pages snapshot gần nhất (khớp permalink bỏ query/trailing-slash, không khớp thì thử slug từ khóa có biên path — "noi-mi" không ăn của "noi-mi-quan-2"), **AEO** engine nhắc / đã hỏi (khớp fold từ khóa, bỏ dấu), **Submit** theo state IndexNow, và **trạng thái**: 🔴 đang kéo (clicks>0) / 🟡 hiển thị chưa ai bấm (imps>0) / ⚫ lẻo (có trong GSC nhưng 0 imps) / chưa có dữ liệu GSC (bài mới cần vài ngày) / draft chờ duyệt — kèm 1 dòng khuyên (review title/meta, gắn link nội bộ, `--indexnow`, dán lại câu trả lời AI). Bài đã push mà còn draft cũ cùng từ khóa thì draft bị bỏ (không đếm đôi). Xem cả trong `--html-report` section "Hiệu quả từng bài viết". Ghép 5 nguồn có sẵn — 0 request mới; tool chỉ READ và khuyên.

---

### 20. IndexNow — đẩy URL mới vào Bing/Yandex/Seznam/Naver (T18)

- **`--indexnow`** (T18): đổi trang mới đăng/sửa → nói ngay cho **các engine ngoài Google** qua IndexNow (`https://api.indexnow.org/indexnow`, tiêu chuẩn mở — engine nào nhận tự share cho các engine còn lại). KHÔNG dùng Bing API key, KHÔNG OAuth, KHÔNG dependency mới: key 32 ký tự hex tự sinh + treo 1 file text lên site để verify. Setup 1 lần (~10 phút, hướng dẫn đầy đủ **[`docs/USE_INDEXNOW.md`](docs/USE_INDEXNOW.md)**).
- **`--indexnow-key`**: sinh key + lưu `data/indexnow_key.txt` (per-site khi migrate), in hướng dẫn 2 cách treo (SFTP gốc site / WP Media) — tool KHÔNG tự upload, việc đụng site của bạn là quyết định của owner.
- **Chống spam**: 1 lần/ngày (state `data/indexnow_state.json`); đánh dấu CHỈ KHI submit thành công — mạng chết thì lần chạy kế tự thử lại. `--force` submit lại bất chấp; `--dry-run` xem sẽ submit gì (không gọi mạng, không có key vẫn chạy).
- **URL mới từ sitemap (T24)**: `python main.py --indexnow` KHÔNG chỉ định URL giờ tự GET **sitemap.xml của site** (robots khai `Sitemap:` trước, thiếu thì `/sitemap.xml`; sitemap index đọc tối đa 10 file con — cùng luật robots + cùng host như audit, tối đa 1 + 3 + 10 request XML), đóng với cấu hình đã biết (lần submit trước trong state `known` + audit gần nhất + rank history + trang chủ) → **chỉ submit URL MỚI**; submit xong tự nhớ vào `known` nên lần sau không gửi lại chính nó. Không có URL mới → in ra và không submit gì (tiết kiệm endpoint). `--indexnow-full` đẩy lại toàn bộ sitemap (vẫn tôn trọng 1 lần/ngày, `--force` để bất chấp); sitemap lỗi/rỗng rơi đúng nguồn cũ (audit/rank history/trang chủ) của T18; chỉ định URL tay `--indexnow URL1 URL2` = hành vi T18 nguyên vẹn.

---

## Cài đặt

Yêu cầu Python 3.10+ (dùng `dict[str, Any]`, `tuple[bool, str]`).

```bash
# 1. Tạo môi trường ảo (khuyên dùng)
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate    # Linux/macOS

# 2. Cài dependencies
pip install -r requirements.txt

# 3. Cài browser cho Playwright
playwright install chromium
```

**Cách 1 lệnh (Windows):** double-click **`run.bat`** — tự tìm Python (`python`/`py -3`), tạo `venv` nếu chưa có, `pip install -r requirements.txt`, `playwright install chromium`, rồi mở **GUI** (`ui.py`). Truyền tham số thì chạy CLI thay GUI: `run.bat --rank` → `python main.py --rank`. Mỗi lần chạy lại dùng venv có sẵn — các bước cài đặt bị bỏ qua nên nhanh.

**Tùy chọn — AI Engine (Ollama)**: persona hiện sinh bằng thuật toán có chủ ý, không cần LLM. Muốn dùng Ollama (dự phòng cho content generation):

```bash
ollama pull qwen3:30b-a3b
```

## Cách chạy

### GUI (khuyến nghị)

```bash
python ui.py
```

Giao diện CustomTkinter dark mode với 7 tab cấu hình:

| Tab | Cấu hình |
|---|---|
| ⚙️ Cài Đặt Chung | URL target, chế độ traffic (direct/search/aio/mix), số luồng |
| 🔁 Treo Máy | Bật/tắt loop, thời gian treo máy |
| 🖥️ Thiết Bị | Headless, tải ảnh, chọn thiết bị giả lập |
| 🎯 Hành Vi SEO | Thời gian onsite min/max, pogo-stick, third page, warm-up search |
| 🤖 AI Engine | URL Ollama, chọn model, kiểm tra kết nối |
| 🔥 Nuôi Nick | Bật/tắt từng kênh warm-up (YouTube, báo, wiki, shopping, FB, IG) |
| 📈 Xếp Hạng | Báo cáo gộp SERP + Search Console, nút check rank, nút lấy GSC, nút xuất CSV, nút audit site, nút check backlink, nút xuất HTML / link nội bộ / việc ưu tiên / doctor, khung từ khóa đề xuất, khung lịch tự động |

Sidebar hiển thị: đếm session ✅/❌, đồng hồ đếm ngược treo máy, trạng thái Ollama.

### CLI

```bash
python main.py             # Xem tổng quan chiến lược (content + keyword + backlink)
python main.py --search    # Chạy automation mode search (qua Google, có rate-limit)
python main.py --direct    # Chạy automation mode direct
python main.py --plan      # Xem content plan 30 ngày
python main.py --keywords  # Xem keyword research
python main.py --backlinks # Xem backlink strategy
python main.py --rank       # Kiểm tra vị trí từ khóa trên Google (+ lưu lịch sử)
python main.py --rank-report # Xem báo cáo xếp hạng đã lưu
python main.py --gsc        # Lấy dữ liệu Search Console (clicks/impressions)
python main.py --gsc-report # Xem báo cáo Search Console đã lưu
python main.py --gsc-keywords  # Từ khóa đề xuất từ query Search Console (chưa theo dõi)
python main.py --gsc-add-keyword "nối mi quận 7"   # Thêm 1 từ khóa vào theo dõi (+ --yes)
python main.py --export rank|gsc|audit|backlinks|plan|all  # Xuất CSV (mở Excel); `all` = cả 5 loại, trống vẫn ra file
python main.py --alerts    # Cảnh báo tụt hạng đang chờ + kênh giao hàng (Telegram/console)
python main.py --weekly    # Báo cáo tuần gộp SERP+GSC+AEO → 1 tin Telegram (1 lần/tuần, --force gửi lại)
python main.py --daily-report [-save]  # Báo cáo buổi sáng 1 tin: rank tail + GSC tail + việc hôm nay
python main.py --run-job rank|gsc|backlink|report|daily|traffic  # Gọi 1 job (Windows Task Scheduler dùng lệnh này)
python main.py --scheduler-status  # Job nào tới giờ chạy, kết quả/lỗi lần cuối, 5 lần gần nhất
python main.py --doctor [--net]  # Kiểm tra môi trường 1 lệnh: site/từ khóa, GSC, Telegram, Ollama, backlink, WP, nháp
python main.py --audit [--audit-limit 30]  # Audit on-page site của mình (HTML tĩnh, chỉ cùng domain)
python main.py --audit-actions [--limit 5]  # Finding audit → việc ưu tiên theo từ khóa (CAO trước)
python main.py --wp-push content/drafts/<file>.md  # Đẩy 1 bản nháp lên WP (CHỈ status draft/pending)
python main.py --pagespeed [URL]  # Core Web Vitals (LCP/CLS/INP) từ PageSpeed Insights — số LAB
python main.py --backlink-check [--backlink-limit 20]  # Verify link đã đặt: còn sống + còn link tới site + dofollow
python main.py --backlink-add "https://site-khac/bai-cua-ban"  # Thêm 1 backlink vào config/backlinks.json
python main.py --backlink-import <file.csv>  # Nạp CSV "External links" tải tay từ Search Console
python main.py --backlink-refresh  # Check lại toàn bộ, bỏ qua cache 24h
python main.py --generate "nối mi tự nhiên"  # Sinh dàn ý + draft vào content/drafts/ (Ollama local)
python main.py --generate --day 3  # Lấy mục ngày 3 trong content plan 30 ngày để sinh bài
python main.py --generate "kw" --dry-run  # Chỉ in prompt, không gọi Ollama, không tạo file
python main.py --migrate-multi-site --dry-run  # Xem trước: sẽ copy dữ liệu site hiện tại vào data/<slug>/ gì (không ghi)
python main.py --migrate-multi-site  # Copy (CHỈ copy, không xoá gốc) vào data/<slug>/ + config/<slug>/ → bật per-site
python main.py --site domain.com --rank  # Chạy lệnh cho MỘT site khác (site phải đã migrate) trong cùng project
python main.py --sites  # Xem sổ site (config/sites.json) + site nào dữ liệu đã tách riêng
python main.py --site-add "https://web.com" [--label "..."]  # Thêm site vào sổ (site nên đã migrate)
python main.py --site-remove "https://web.com"  # Bỏ site khỏi sổ (dữ liệu data/<slug>/ không bị xóa)
python main.py --sites-run "--rank"  # Chạy lệnh qua TỪNG site trong sổ (process con mỗi site)
python main.py --aeo-report  # Xem AI engine nào đang nhắc brand (theo từ khóa dán tay)
python main.py --aeo-check file.txt --aeo-keyword "nối mi" --aeo-engine ChatGPT  # Lưu 1 câu trả lời AI đã copy
python main.py --html-report  # Gộp rank + GSC + audit + backlink → data/report.html (1 file, mở offline)
python main.py --internal-links  # Gợi ý trang site nên chèn link nội bộ theo từng từ khóa (từ audit + rank history)
python main.py --competitors  # Domain đối thủ xuất hiện nhiều nhất trong top URLs đã lưu
python main.py --keyword-groups  # Nhóm từ khóa trùng token + bài nên refresh + hiệu năng theo cụm
python main.py --cluster-gsc  # Cụm từ khóa theo dữ liệu Google thật: imps/clicks GSC + cụm mù GSC
python main.py --rank-urls  # Trang nào đang rank cho từ nào + cảnh báo đổi trang (từ top_urls đã lưu)
python main.py --ctr-ops  # Query được thấy mà ít người click — nên sửa title/meta (từ snapshot GSC)
python main.py --gsc-pages  # Query nào do nhiều trang phục vụ / trang nào gánh nhiều query (Google thật)
python main.py --page-impact  # Sức nặng theo trang: trang VIP (👑), phơi không ai click, bảng % imps
python main.py --content-gap  # Query Google phơi mà site chưa có trang riêng (Google mượn trang chủ)
python main.py --refresh-diff  # Bài nên refresh đã đến bước nào: chưa draft / chờ duyệt / đã push
python main.py --content-brief "kw" [-save]  # Brief trộn dữ liệu cho 1 từ khóa (cụm + SERP + GSC + plan)
python main.py --va-pack  # Gói việc ngày cho VA — 1 file md checklist (data/<slug>/va_pack_<ngay>.md)
python main.py --yoast-meta <post_id> --kw "tu khoa"  # Patch Yoast focuskw/meta cho bai draft/pending sau --wp-push
python main.py --setup-wizard  # Wizard cai dat lan dau — buoc nao xong, con thieu gi (docs nao de lam)
python main.py --first-run  # Chay thu tuan tu lan dau: wizard → doctor → audit → export CSV + viec ke tiep
python main.py --gsc-trend  # Xu hướng imps/clicks/CTR theo query, 8 mốc gần nhất + cờ sụt sớm
python main.py --gsc-alerts  # Canh bao imps rut manh (<50% hoac mat) giua 2 snapshot GSC
python main.py --audit-diff  # Lỗi mới phát hiện vs đã sửa, giữa 2 lần audit gần nhất
python main.py --plan-progress  # 30 muc plan: muc nao da co draft / da push WP, ke tiep thi generate
python main.py --aeo-questions "nối mi quận 7" [--aeo-angle best,compare,local]  # Sinh biến thể câu hỏi AEO để dán tay
python main.py --ai-robots  # Bot AI nào bị robots.txt chặn (1 request, chỉ báo cáo — không tự sửa)
```

Mode `--search`/`--direct` kiểm tra rate limiter trước khi chạy và thoát nếu vượt giới hạn.

## Cấu hình chính (`config/settings.py`)

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `TARGET_URL` | `https://nankybeauty.com/` | Website mục tiêu |
| `TRAFFIC_MODE` | `"search"` | direct / search / aio / mix |
| `DEVICE_NAME` | Random Mobile 70 | Thiết bị giả lập |
| `MAX_SESSIONS_PER_DAY` | `25` | Giới hạn session mỗi ngày |
| `MIN_INTERVAL_BETWEEN_SESSIONS` | `300` | Giây tối thiểu giữa 2 session |
| `DURATION_MIN` / `DURATION_MAX` | 45 / 180 | Thời gian onsite (giây) |
| `PEAK_HOURS_ENABLE` | `True` | Chạy nhiều hơn vào giờ cao điểm VN |
| `WARMUP_*` | `True` | Bật/tắt từng kênh nuôi nick |
| `POGO_STICK_ENABLE` | `False` | Pogo-stick (tắt để an toàn) |
| `RANK_CHECK_DEPTH` | `100` | Rank tracker: tìm domain trong top N kết quả |
| `RANK_CHECK_MAX_PER_DAY` | `3` | Rank tracker: số lần check tối đa mỗi ngày |
| `GSC_SITE_URL` | `sc-domain:nankybeauty.com` | Search Console: property lấy dữ liệu |
| `GSC_CREDENTIALS_FILE` | `config/gsc_service_account.json` | Search Console: file key service account |
| `GSC_LOOKBACK_DAYS` | `28` | Search Console: lấy dữ liệu N ngày gần nhất |
| `GSC_MAX_FETCH_PER_DAY` | `4` | Search Console: số lần fetch tối đa mỗi ngày |
| `KEYWORD_SUGGEST_MIN_IMPRESSIONS` | `30` | Search Console: ngưỡng impressions để một query được đề xuất làm từ khóa mới |
| `KEYWORD_SUGGEST_LIMIT` | `20` | Số từ khóa đề xuất hiển thị tối đa mỗi lần |
| `ALERTS_ENABLE` | `False` | Cảnh báo: bật mới gửi Telegram; tắt thì chỉ in console |
| `RANK_ALERT_DROP` | `5` | Cảnh báo: hạng rơi ≥ N vị trí so với lần check liền trước thì báo |
| `RANK_ALERT_TOP10_FALL` | `True` | Cảnh báo: đang trong Top 10 mà rớt ra ngoài thì báo |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | `""` | Cảnh báo: nên để ở **biến môi trường** (thắng settings.py) — xem `docs/SETUP_ALERTS.md` |
| `ALERTS_STATE_DIR` | `data` | Nơi lưu `alerts_state.json` (state chống spam 1 tin/ngày/từ khóa) |
| `RANK_ALERT_TREND_ENABLE` | `True` | Cảnh báo (C4): rule xu hướng bật sẵn — tắt nếu chỉ muốn rule tụt đột ngột |
| `RANK_ALERT_TREND_DROP` | `3` | Cảnh báo (C4): trung bình hạng 4 mốc mới xấu đi ≥ N vị trí so với 4 mốc cũ → 🌡️ dự báo |
| `RANK_ALERT_TREND_WINDOW` | `14` | Cảnh báo (C4): số lần check gần nhất được nhìn |
| `SCHEDULER_RANK_HOURS` / `SCHEDULER_GSC_HOURS` | `[7, 13, 19]` / `[9]` | Lịch **mong muốn** — chỉ để in ra status; giờ thật phải sửa trên Windows Task Scheduler |
| `SCHEDULER_BACKLINK_HOURS` | `[]` | Lịch job verify backlink — rỗng = không tự chạy, chỉ `--run-job backlink` tay |
| `SCHEDULER_NOTIFY_ENABLE` | `False` | 1 tin Telegram tóm tắt sau mỗi job (cần `ALERTS_ENABLE=True` mới có kênh gửi) |
| `SCHEDULER_TRAFFIC_ENABLE` | `False` | Cho phép lịch tự chạy session traffic — mặc định TẮT, bật là quyết định của owner |
| `SCHEDULER_LOCK_STALE` | `1200` | Giây không heartbeat thì lock bị coi là đã chết, job khác giành quyền chạy |
| `AUDIT_MAX_PAGES` | `100` | Audit: số trang tối đa mỗi lần `--audit` (`--audit-limit N` để đổi từng lần) |
| `AUDIT_TIMEOUT` | `10` | Audit: giây/request — link hỏng không được treo cả đợt audit |
| `AUDIT_USER_AGENT` | UA Chrome desktop | Audit: UA tĩnh khi xin HTML — chỉ đọc site của chính bạn, không phải Googlebot |
| `AUDIT_STATE_DIR` | `data` | Nơi lưu `audit_last.json` (kết quả lần audit gần nhất, để `--export audit` đọc lại) |
| `PAGESPEED_TIMEOUT` | `90` | PageSpeed: giây/lượt — PSI tự chạy Lighthouse nên chậm hơn crawl nhiều |
| `PAGESPEED_STATE_DIR` | `data` | Nơi lưu `pagespeed.json` (chỉ số gọn, không chứa response thô) |
| `PAGESPEED_API_KEY` | `""` | PageSpeed: để trống vẫn chạy; điền key miễn phí khi quota ẩn danh (dùng chung toàn cầu) hết. **Secret** — đừng commit, đừng in ra log |
| `PAGESPEED_WARN_SCORE` | `60` | PageSpeed bài viết (T33): điểm LAB mobile dưới mốc → 1 dòng nhắc trong báo cáo ngày |
| `PAGESPEED_MAX_PER_RUN` | `5` | PageSpeed bài viết (T33): mỗi đợt job đo tối đa N URL mới (Lighthouse mất chục giây/URL) |
| `SCHEDULER_PAGESPEED_HOURS` | `[6]` | Giờ job `pagespeed` chạy mỗi ngày — đo bài mới push chưa có điểm (1 request/URL trọn đời) |
| `BACKLINK_PARALLEL` | `5` | Backlink: số luồng tối đa khi check — mức lịch sự với site người khác, không bao giờ vượt số URL của đợt |
| `BACKLINK_TIMEOUT` | `15` | Backlink: giây/request — một trang treo không được giữ cả đợt check |
| `BACKLINK_CACHE_HOURS` | `24` | Backlink: URL đã check trong N giờ thì dùng kết quả cũ (`--backlink-refresh` để bỏ qua) |
| `BACKLINK_STATE_DIR` | `data` | Nơi lưu `backlink_status.json` (kết quả check, để `--export backlinks` đọc lại) |
| `BACKLINK_STORE_FILE` | `backlinks.json` | Tên file danh sách link đã đặt, nằm trong `config/` — **đã gitignore** vì là dữ liệu kinh doanh |
| `OUTREACH_REMIND_PROPOSED` | `7` | Sổ outreach (T32): đề xuất đã gửi N ngày chưa phản hồi → nhắc follow-up trong báo cáo ngày |
| `OUTREACH_REMIND_AGREED` | `5` | Sổ outreach (T32): người ta đồng ý N ngày mà chưa đặt link → nhắc gửi anchor / đánh dead |
| `OUTREACH_STATE_DIR` | `data` | Nơi lưu `outreach.json` (sổ lời đề xuất — gitignored) |
| `CONTENT_MODEL` | `qwen3:30b-a3b` | Content (F8): model Ollama sinh bài — bản nháp, owner duyệt rồi mới dùng |
| `CONTENT_GEN_TIMEOUT` | `300` | Content: giây/lượt gọi Ollama — model 30b chậm, draft dài cần thời gian |
| `CONTENT_GEN_RETRIES` | `1` | Content: số lần retry, **chỉ khi timeout**; connection error báo ngay không retry |
| `CONTENT_DRAFTS_DIR` | `content/drafts` | Content: nơi lưu bản nháp `.md` (UTF-8, **gitignore** — dữ liệu nháp riêng) |
| `AEO_BRANDS` | `["Nanky Beauty", "nankybeauty.com", "nanky beauty"]` | AEO: biến thể brand cần nhận ra (so bỏ dấu, từ trọn vẹn) — thêm biến thể mới của bạn vào đây |
| `AEO_HISTORY_KEEP` | `500` | AEO: số bản ghi tối đa lưu trong `aeo_history.json` — cũ nhất bị cắt |
| `AEO_COMPETITORS` | `{"name-A": ["name A", "namea.com"], "name-B": ["name B"]}` (placeholder) | AEO share-of-voice (T23): dict `{tên đối thủ: [biến thể]}` — cùng luật brand mình (bỏ dấu, token trọn vẹn); đếm đối thủ được nhắc trong CÙNG câu trả lời AI; `{}` = tắt tính năng |
| `WP_URL` / `WP_USER` | `""` | WordPress (C1): site + username để đẩy bản nháp; để trống → `--wp-push` báo hướng dẫn |
| `WP_APP_PASSWORD` | `""` | WordPress: **App Password** (WP admin → Profile → Application Passwords) — nên để biến môi trường `WP_APP_PASSWORD` (thắng settings) |
| `WP_DEFAULT_CATEGORIES` / `WP_DEFAULT_TAGS` | `[]` | WordPress (P2-4): TÊN category/tag gán mặc định khi `--wp-push` — tool tra id, term chưa có trên WP bị bỏ qua + cảnh báo (không tự tạo); `[]` = không gán |

Danh sách từ khóa **không nằm trong settings.py**: nó ở `config/keywords.json`
(`{"site": "...", "keywords": [...]}`), đọc/sửa qua tab ⚙️ Cài Đặt Chung (textarea "Từ khóa Google SEO"),
nút **+ Thêm** ở khung đề xuất tab 📈 Xếp Hạng, hoặc `python main.py --gsc-add-keyword "..."`.
Sửa tay file này phải giữ JSON hợp lệ — mã hỏng thì tool coi như danh sách rỗng.

Danh sách backlink đã đặt cũng **không nằm trong settings.py**: nó ở `config/backlinks.json`
(`{"site": "...", "links": [{"url", "note", "added"}]}`), thêm qua `--backlink-add` /
`--backlink-import`, còn kết quả check nằm ở `data/backlink_status.json`.

## Cấu trúc project

```
seo-by-Tung/
├── main.py                  # CLI entry point
├── ui.py                    # GUI (CustomTkinter, 7 tab)
├── fix_encoding.py          # Tool sửa lỗi encoding tiếng Việt trong source
├── config/
│   ├── settings.py          # Toàn bộ cấu hình
│   ├── keywords.json        # Danh sách từ khóa đang theo dõi (nguồn sự thật duy nhất)
│   └── backlinks.json       # Danh sách backlink **đã đặt** (--backlink-add/import; gitignore vì là dữ liệu riêng)
├── core/
│   └── browser_manager.py   # Launch browser, fingerprint anti-detect, profile
├── scenarios/
│   ├── warmup.py            # Nuôi nick: YouTube, báo, wiki, shopping, FB, IG
│   └── aio_traffic.py       # AIO flow: hỏi AI → search Google → click
├── utils/
│   ├── ai_engine.py         # Persona & search behavior engine
│   ├── interactions.py      # Scroll, click, sleep tự nhiên
│   ├── mouse_helper.py      # Di chuột cong như người
│   ├── onsite_interactions.py # CTA, tabs, gallery, form, search onsite
│   ├── rank_tracker.py      # Theo dõi vị trí từ khóa trên Google
│   ├── gsc_client.py        # Google Search Console API client + báo cáo gộp
│   ├── keywords.py          # Đọc/ghi/add từ khóa (config/keywords.json)
│   ├── site_paths.py        # Multi-site (F10): slug từ domain + resolver đường dẫn per-site (fallback phẳng)
│   ├── migrate_sites.py     # Multi-site (F10): --migrate-multi-site — CHỈ copy, không xoá gốc
│   ├── exporter.py          # Xuất CSV (UTF-8 BOM) lịch sử xếp hạng + Search Console + kết quả audit
│   ├── alerts.py            # Cảnh báo tụt hạng: rules engine + chống spam + Telegram sender
│   ├── scheduler.py         # Lịch tự động: bảng job + lock + state (đồng hồ ở Windows Task Scheduler)
│   ├── html_probe.py        # Audit: HTML string → dict (stdlib html.parser, không dependency mới)
│   ├── site_auditor.py      # Audit: 20 rule on-page + crawler chỉ chạm domain mục tiêu, có robots.txt
│   ├── pagespeed.py         # Core Web Vitals qua PageSpeed Insights API (số LAB, lưu data/pagespeed.json)
│   ├── backlinks.py         # Backlink: store config/backlinks.json + state + verify thuần (tái dùng html_probe)
│   ├── backlink_checker.py  # Backlink: batch fetch requests ≤5 luồng, cache 24h, báo cáo %sống/%link/dofollow
│   ├── content_prompts.py   # Content (F8): slugify + prompt outline/draft + frontmatter + seo_check — thuần, không network
│   ├── ollama_client.py     # Content (F8): client Ollama localhost (stream=False, chỉ retry khi timeout)
│   ├── automation.py        # 1 session traffic — main.py --auto và scheduler dùng chung
│   └── rate_limiter.py      # Giới hạn 25 session/ngày + cooldown
├── tests/
│   ├── test_search_flow.py  # Search flow: Google → SERP → click target
│   └── test_direct_access.py# Deep session truy cập trực tiếp
├── content/
│   ├── planner.py           # Content plan 30 ngày
│   ├── keyword_research.py  # Volume/difficulty/intent + funnel
│   ├── generator.py         # F8: pipeline outline→draft→file (atomic, UTF-8 không BOM), CLI --generate
│   └── drafts/              # (sinh ra khi chạy) bản nháp .md — gitignore, owner duyệt rồi mới dùng
├── backlinks/
│   └── tracker.py           # Backlink 3 tier + guest post targets = danh sách **cơ hội** (todo), không phải link đã đặt
├── profiles/                # (sinh ra khi chạy) cookie/localStorage theo profile
├── reports/                 # (sinh ra khi chạy) CSV xuất từ --export / nút XUẤT CSV
└── data/                    # (sinh ra khi chạy) alerts_state.json + scheduler_state.json/scheduler.lock
                             #   + audit_last.json + pagespeed.json + backlink_status.json
                             # F10: sau --migrate-multi-site, mỗi site có data/<slug>/ + config/<slug>/ riêng
                             #   (file phẳng gốc được GIỮ NGUYÊN — bạn tự xoá sau khi kiểm tra per-site đọc đúng)
```

## Xử lý sự cố

- **Bị CAPTCHA thường xuyên**: kiểm tra `locale`/`timezone`/`Accept-Language` đã khớp (mặc định đã force `vi-VN`); giữ nguyên file trong `profiles/`; giảm `MAX_SESSIONS_PER_DAY`; cân nhắc dùng proxy VN.
- **Gõ lệnh `python ui.py` báo thiếu module**: chưa `pip install -r requirements.txt` hoặc đang sai môi trường ảo.
- **Playwright không mở được browser**: chạy `playwright install chromium`.
- **`--generate` báo "Chưa chạy Ollama tại localhost:11434"**: chưa bật `ollama serve` (hoặc chưa `ollama pull qwen3:30b-a3b`). Tool chỉ nói chuyện với Ollama local, **không** thêm dependency AI nào, **không** gửi prompt ra ngoài máy — dùng `--dry-run` để xem prompt mà không cần Ollama.
- **Ký tự tiếng Việt hiển thị `?` trong source**: một số file comment bị hỏng encoding (lịch sử lưu ANSI). Chạy `python fix_encoding.py` để sửa các chuỗi quen thuộc, hoặc mở file và lưu lại với encoding UTF-8.
- **`--audit` báo "Không đọc được trang nào" (exit 1)**: sai `TARGET_URL` hoặc mất mạng; nếu site tự chặn UA desktop thì crawler chỉ ghi nhận 403/429 thành một dòng báo cáo — **không** retry và **không** đổi UA để lọt qua (đó là việc của lớp anti-detect, đã tuyên bố không đụng tới).
- **`--pagespeed` trả 429 "hết quota"**: quota ẩn danh của PSI là *Queries per day* dùng chung toàn cầu — hết thì chờ hoặc tạo key miễn phí rồi điền `PAGESPEED_API_KEY`; báo cáo audit HTML không liên quan vẫn chạy.
- **`--backlink-check` báo "Bị chặn (403)" hoặc "không đọc được"**: site đó chặn UA desktop hoặc mạng chậm — đó là **một dòng báo cáo**, không phải link chết, và tool **không** retry hay đổi UA để lọt qua. Muốn check lại ngay: `--backlink-refresh` (bỏ cache 24h). Danh sách trống thì lệnh exit 2 và chỉ cách thêm (`--backlink-add`, `--backlink-import`).
- **`--site domain.com` nhưng dữ liệu vẫn là của site cũ / rỗng**: site đó **chưa migrate** — khi thiếu dấu `data/<slug>/.migrated`, resolver rơi về file phẳng gốc (1 site). Chạy `python main.py --migrate-multi-site` cho site muốn tách, rồi `--site` mới trỏ vào dữ liệu riêng. GUI báo rõ `per-site=BẬT/TẮT` khi bấm **🔀 Áp dụng site**.
- **Lo sợ migrate làm mất dữ liệu**: `--migrate-multi-site` **chỉ `shutil.copy2`**, không `os.remove`/`move` file gốc bao giờ; muốn an toàn chạy `--dry-run` trước. Credential `config/gsc_service_account.json` không nằm trong danh sách copy.

## Giới hạn phụ thuộc

`requirements.txt` gồm: `playwright`, `playwright-stealth`, `customtkinter`, `requests`, `fake-useragent`. `playwright-stealth` là tùy chọn — nếu chưa cài, tool vẫn chạy nhưng bỏ qua lớp stealth bổ sung.

Audit (F6) **không thêm dependency nào**: bóc HTML dùng `html.parser` của stdlib (`utils/html_probe.py`) thay vì beautifulsoup4, crawl bằng `requests` đã có sẵn, PageSpeed gọi thẳng API không cần thư viện Google.

Backlink check (F7) cũng **không thêm dependency**: tái dùng `html_probe` để bóc link và `requests` (ThreadPool của stdlib) để fetch — không Playwright, vì backlink là HTML tĩnh của trang người khác, không cần render.
