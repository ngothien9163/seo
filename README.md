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
- Setup service account Google ~10 phút, làm 1 lần: xem **[docs/SETUP_GSC.md](docs/SETUP_GSC.md)**.

### 8. Xuất báo cáo CSV — mang dữ liệu đi nơi khác

- `--export rank` xuất **toàn bộ lịch sử xếp hạng** (một dòng mỗi lần check × mỗi từ khóa), `--export gsc` xuất các query của snapshot Search Console mới nhất, `--export audit` xuất các lỗi của lần `--audit` gần nhất, `--export all` (mặc định) ra cả hai file **định kỳ** (rank + gsc — audit không đi kèm vì phải tự crawl trước).
- Mã **UTF-8 có BOM** → mở trực tiếp bằng Excel bản tiếng Việt không lỗi dấu; CTR xuất dạng số đã ×100 (không kèm ký hiệu `%`) để Excel còn tính toán được.
- File ghi vào `reports/export_<ngày>_<giờ>_<rank|gsc|audit>.csv`, **mỗi lần export một file mới** — không ghi đè lần trước. Chưa có dữ liệu thì file vẫn được ghi (chỉ có dòng tiêu đề) để quy trình không gãy.
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

---

### 11. Lịch chạy tự động — Windows Task Scheduler (F4)

- **Đồng hồ không nằm trong code.** Windows Task Scheduler gọi `python main.py --run-job rank|gsc|traffic` đúng giờ; `utils/scheduler.py` chỉ quyết định "giờ này có được chạy không", chặn hai job chồng nhau (`data/scheduler.lock` — PID + heartbeat, stale 20 phút) và ghi dấu vết vào `data/scheduler_state.json`.
- **Không tự nới giới hạn.** Job `rank` vẫn bị `RANK_CHECK_MAX_PER_DAY`/`RANK_CHECK_MIN_INTERVAL` chặn, `gsc` vẫn bị `GSC_MAX_FETCH_PER_DAY`, `traffic` vẫn bị rate limiter — scheduler gọi lại đúng hàm check của module gốc chứ không đếm riêng.
- **Traffic mặc định TẮT tự chạy** (`SCHEDULER_TRAFFIC_ENABLE = False`): bật lên là quyết định của bạn, vì chạy lúc không có ai nhìn thì lỗi tích âm thầm.
- **Không chạy bù**: máy tắt đúng giờ thì mất lượt trong ngày — không gom nhiều lần check một lúc cho đỡ "phí".
- **Chạy nền không ngồi chờ**: job `rank` gặp CAPTCHA thì bỏ qua từ khóa đó (khác với bấm `--rank` trong GUI, có ô hỏi người giải).
- Xem lại: `python main.py --scheduler-status` (job nào chạy lúc nào, exit code, lỗi cuối, 5 lần gần nhất) hoặc khung **🗓 LỊCH TỰ ĐỘNG** trong tab 📈 Xếp Hạng. GUI cố ý **không** có nút chạy job — muốn chạy tay thì dùng CLI để log nằm đúng chỗ.
- Đăng ký lịch từng bước (4 lệnh `schtasks`): **[`docs/SETUP_SCHEDULER.md`](docs/SETUP_SCHEDULER.md)**.

---

### 12. Audit on-page + Core Web Vitals (F6)

- `python main.py --audit` crawl **chính site trong `TARGET_URL`** (tối đa `AUDIT_MAX_PAGES` trang, `AUDIT_TIMEOUT` giây/trang) bằng **HTML tĩnh qua `requests`** — không mở trình duyệt, không đụng lớp anti-detect, và **không bao giờ** request ra ngoài domain của bạn (kể cả link ngoài hay sitemap trỏ host khác).
- 20 rule on-page, mỗi lỗi in kèm **severity + URL**: thiếu `title` / title dài ngắn bất thường / thiếu `meta description` / meta quá dài / thiếu `H1` / nhiều `H1` / heading nhảy cấp / ảnh thiếu `alt` / `alt=""` hàng loạt / thiếu `canonical` / `canonical` đáng ngờ / `noindex` lạc chỗ / link `http://` nội bộ / thiếu `lang` / **link nội bộ hỏng (404, 410)** / trang không đọc được / `title` trùng giữa các trang / thiếu `sitemap.xml` / URL bị robots chặn.
- **Tôn trọng `robots.txt`** của site mình (tự parse theo quy tắc Google: đường dẫn khớp **dài nhất** thắng — `urllib.robotparser` 3.11 khớp theo thứ tự khai báo nên đã đo và không dùng), ưu tiên URL lấy từ `sitemap.xml`, không có sitemap thì lần theo link nội bộ. Trang 404/5xx/timeout là **một dòng báo cáo**, không làm dừng cả đợt.
- Kết quả lưu vào `data/audit_last.json` → `python main.py --export audit` ra CSV (`severity,rule,url,detail`, UTF-8 BOM) mở bằng Excel. GUI: tab **📈 Xếp Hạng** → nút **🔍 AUDIT SITE** (thread nền, log in ra khung, chạy xong tự xuất CSV).
- `python main.py --pagespeed [URL]`: **LCP / CLS / INP** + điểm hiệu năng, cả mobile lẫn desktop, qua PageSpeed Insights API; chỉ lưu số gọn trong `data/pagespeed.json` (không lưu response thô, vài MB).
- Số PSI là **LAB** (Lighthouse do Google chạy hộ lúc gọi), **không phải field data CrUX**. API **không cần key**, nhưng quota ẩn danh là *"Queries per day" dùng chung toàn cầu* — **đo thật 2026-10-14: đang cạn**, nên lệnh hiện trả thông báo 429 và exit 1. Muốn có số: tạo key miễn phí rồi điền `PAGESPEED_API_KEY` (key là secret của bạn — code không in ra log, không ghi vào file).
- HTML tĩnh **không phải Googlebot**: nội dung render bằng JS không được soi, và thứ hạng thật có thể khác những gì HTML thể hiện. `--audit-limit N` để thu hẹp/mở rộng số trang crawl.

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
| 📈 Xếp Hạng | Báo cáo gộp SERP + Search Console, nút check rank, nút lấy GSC, nút xuất CSV, nút audit site, nút check backlink, khung từ khóa đề xuất, khung lịch tự động |

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
python main.py --export rank|gsc|audit|backlinks|all  # Xuất CSV (mở Excel); `all` = rank + gsc (audit/backlinks phải chạy trước)
python main.py --alerts    # Cảnh báo tụt hạng đang chờ + kênh giao hàng (Telegram/console)
python main.py --run-job rank|gsc|traffic  # Gọi 1 job (Windows Task Scheduler dùng lệnh này)
python main.py --scheduler-status  # Job nào tới giờ chạy, kết quả/lỗi lần cuối, 5 lần gần nhất
python main.py --audit [--audit-limit 30]  # Audit on-page site của mình (HTML tĩnh, chỉ cùng domain)
python main.py --pagespeed [URL]  # Core Web Vitals (LCP/CLS/INP) từ PageSpeed Insights — số LAB
python main.py --backlink-check [--backlink-limit 20]  # Verify link đã đặt: còn sống + còn link tới site + dofollow
python main.py --backlink-add "https://site-khac/bai-cua-ban"  # Thêm 1 backlink vào config/backlinks.json
python main.py --backlink-import <file.csv>  # Nạp CSV "External links" tải tay từ Search Console
python main.py --backlink-refresh  # Check lại toàn bộ, bỏ qua cache 24h
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
| `SCHEDULER_RANK_HOURS` / `SCHEDULER_GSC_HOURS` | `[7, 13, 19]` / `[9]` | Lịch **mong muốn** — chỉ để in ra status; giờ thật phải sửa trên Windows Task Scheduler |
| `SCHEDULER_TRAFFIC_ENABLE` | `False` | Cho phép lịch tự chạy session traffic — mặc định TẮT, bật là quyết định của owner |
| `SCHEDULER_LOCK_STALE` | `1200` | Giây không heartbeat thì lock bị coi là đã chết, job khác giành quyền chạy |
| `AUDIT_MAX_PAGES` | `100` | Audit: số trang tối đa mỗi lần `--audit` (`--audit-limit N` để đổi từng lần) |
| `AUDIT_TIMEOUT` | `10` | Audit: giây/request — link hỏng không được treo cả đợt audit |
| `AUDIT_USER_AGENT` | UA Chrome desktop | Audit: UA tĩnh khi xin HTML — chỉ đọc site của chính bạn, không phải Googlebot |
| `AUDIT_STATE_DIR` | `data` | Nơi lưu `audit_last.json` (kết quả lần audit gần nhất, để `--export audit` đọc lại) |
| `PAGESPEED_TIMEOUT` | `90` | PageSpeed: giây/lượt — PSI tự chạy Lighthouse nên chậm hơn crawl nhiều |
| `PAGESPEED_STATE_DIR` | `data` | Nơi lưu `pagespeed.json` (chỉ số gọn, không chứa response thô) |
| `PAGESPEED_API_KEY` | `""` | PageSpeed: để trống vẫn chạy; điền key miễn phí khi quota ẩn danh (dùng chung toàn cầu) hết. **Secret** — đừng commit, đừng in ra log |
| `BACKLINK_PARALLEL` | `5` | Backlink: số luồng tối đa khi check — mức lịch sự với site người khác, không bao giờ vượt số URL của đợt |
| `BACKLINK_TIMEOUT` | `15` | Backlink: giây/request — một trang treo không được giữ cả đợt check |
| `BACKLINK_CACHE_HOURS` | `24` | Backlink: URL đã check trong N giờ thì dùng kết quả cũ (`--backlink-refresh` để bỏ qua) |
| `BACKLINK_STATE_DIR` | `data` | Nơi lưu `backlink_status.json` (kết quả check, để `--export backlinks` đọc lại) |
| `BACKLINK_STORE_FILE` | `backlinks.json` | Tên file danh sách link đã đặt, nằm trong `config/` — **đã gitignore** vì là dữ liệu kinh doanh |

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
│   ├── exporter.py          # Xuất CSV (UTF-8 BOM) lịch sử xếp hạng + Search Console + kết quả audit
│   ├── alerts.py            # Cảnh báo tụt hạng: rules engine + chống spam + Telegram sender
│   ├── scheduler.py         # Lịch tự động: bảng job + lock + state (đồng hồ ở Windows Task Scheduler)
│   ├── html_probe.py        # Audit: HTML string → dict (stdlib html.parser, không dependency mới)
│   ├── site_auditor.py      # Audit: 20 rule on-page + crawler chỉ chạm domain mục tiêu, có robots.txt
│   ├── pagespeed.py         # Core Web Vitals qua PageSpeed Insights API (số LAB, lưu data/pagespeed.json)
│   ├── backlinks.py         # Backlink: store config/backlinks.json + state + verify thuần (tái dùng html_probe)
│   ├── backlink_checker.py  # Backlink: batch fetch requests ≤5 luồng, cache 24h, báo cáo %sống/%link/dofollow
│   ├── automation.py        # 1 session traffic — main.py --auto và scheduler dùng chung
│   └── rate_limiter.py      # Giới hạn 25 session/ngày + cooldown
├── tests/
│   ├── test_search_flow.py  # Search flow: Google → SERP → click target
│   └── test_direct_access.py# Deep session truy cập trực tiếp
├── content/
│   ├── planner.py           # Content plan 30 ngày
│   └── keyword_research.py  # Volume/difficulty/intent + funnel
├── backlinks/
│   └── tracker.py           # Backlink 3 tier + guest post targets = danh sách **cơ hội** (todo), không phải link đã đặt
├── profiles/                # (sinh ra khi chạy) cookie/localStorage theo profile
├── reports/                 # (sinh ra khi chạy) CSV xuất từ --export / nút XUẤT CSV
└── data/                    # (sinh ra khi chạy) alerts_state.json + scheduler_state.json/scheduler.lock
                             #   + audit_last.json + pagespeed.json + backlink_status.json
```

## Xử lý sự cố

- **Bị CAPTCHA thường xuyên**: kiểm tra `locale`/`timezone`/`Accept-Language` đã khớp (mặc định đã force `vi-VN`); giữ nguyên file trong `profiles/`; giảm `MAX_SESSIONS_PER_DAY`; cân nhắc dùng proxy VN.
- **Gõ lệnh `python ui.py` báo thiếu module**: chưa `pip install -r requirements.txt` hoặc đang sai môi trường ảo.
- **Playwright không mở được browser**: chạy `playwright install chromium`.
- **Ký tự tiếng Việt hiển thị `?` trong source**: một số file comment bị hỏng encoding (lịch sử lưu ANSI). Chạy `python fix_encoding.py` để sửa các chuỗi quen thuộc, hoặc mở file và lưu lại với encoding UTF-8.
- **`--audit` báo "Không đọc được trang nào" (exit 1)**: sai `TARGET_URL` hoặc mất mạng; nếu site tự chặn UA desktop thì crawler chỉ ghi nhận 403/429 thành một dòng báo cáo — **không** retry và **không** đổi UA để lọt qua (đó là việc của lớp anti-detect, đã tuyên bố không đụng tới).
- **`--pagespeed` trả 429 "hết quota"**: quota ẩn danh của PSI là *Queries per day* dùng chung toàn cầu — hết thì chờ hoặc tạo key miễn phí rồi điền `PAGESPEED_API_KEY`; báo cáo audit HTML không liên quan vẫn chạy.
- **`--backlink-check` báo "Bị chặn (403)" hoặc "không đọc được"**: site đó chặn UA desktop hoặc mạng chậm — đó là **một dòng báo cáo**, không phải link chết, và tool **không** retry hay đổi UA để lọt qua. Muốn check lại ngay: `--backlink-refresh` (bỏ cache 24h). Danh sách trống thì lệnh exit 2 và chỉ cách thêm (`--backlink-add`, `--backlink-import`).

## Giới hạn phụ thuộc

`requirements.txt` gồm: `playwright`, `playwright-stealth`, `customtkinter`, `requests`, `fake-useragent`. `playwright-stealth` là tùy chọn — nếu chưa cài, tool vẫn chạy nhưng bỏ qua lớp stealth bổ sung.

Audit (F6) **không thêm dependency nào**: bóc HTML dùng `html.parser` của stdlib (`utils/html_probe.py`) thay vì beautifulsoup4, crawl bằng `requests` đã có sẵn, PageSpeed gọi thẳng API không cần thư viện Google.

Backlink check (F7) cũng **không thêm dependency**: tái dùng `html_probe` để bóc link và `requests` (ThreadPool của stdlib) để fetch — không Playwright, vì backlink là HTML tĩnh của trang người khác, không cần render.
