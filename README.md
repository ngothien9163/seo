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

- `--export rank` xuất **toàn bộ lịch sử xếp hạng** (một dòng mỗi lần check × mỗi từ khóa), `--export gsc` xuất các query của snapshot Search Console mới nhất, `--export all` (mặc định) ra cả hai file.
- Mã **UTF-8 có BOM** → mở trực tiếp bằng Excel bản tiếng Việt không lỗi dấu; CTR xuất dạng số đã ×100 (không kèm ký hiệu `%`) để Excel còn tính toán được.
- File ghi vào `reports/export_<ngày>_<giờ>_<rank|gsc>.csv`, **mỗi lần export một file mới** — không ghi đè lần trước. Chưa có dữ liệu thì file vẫn được ghi (chỉ có dòng tiêu đề) để quy trình không gãy.
- GUI: tab **📈 Xếp Hạng** → nút **📤 XUẤT CSV** (in đường dẫn file ra log).

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
| 📈 Xếp Hạng | Báo cáo gộp SERP + Search Console, nút check rank, nút lấy GSC, nút xuất CSV |

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
python main.py --export rank|gsc|all  # Xuất CSV (mở Excel) lịch sử xếp hạng + Search Console
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

Danh sách từ khóa **không nằm trong settings.py**: nó ở `config/keywords.json`
(`{"site": "...", "keywords": [...]}`), đọc/sửa qua tab ⚙️ Cài Đặt Chung (textarea "Từ khóa Google SEO"),
nút **+ Thêm** ở khung đề xuất tab 📈 Xếp Hạng, hoặc `python main.py --gsc-add-keyword "..."`.
Sửa tay file này phải giữ JSON hợp lệ — mã hỏng thì tool coi như danh sách rỗng.

## Cấu trúc project

```
seo-by-Tung/
├── main.py                  # CLI entry point
├── ui.py                    # GUI (CustomTkinter, 7 tab)
├── fix_encoding.py          # Tool sửa lỗi encoding tiếng Việt trong source
├── config/
│   └── settings.py          # Toàn bộ cấu hình
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
│   ├── exporter.py          # Xuất CSV (UTF-8 BOM) lịch sử xếp hạng + Search Console
│   └── rate_limiter.py      # Giới hạn 25 session/ngày + cooldown
├── tests/
│   ├── test_search_flow.py  # Search flow: Google → SERP → click target
│   └── test_direct_access.py# Deep session truy cập trực tiếp
├── content/
│   ├── planner.py           # Content plan 30 ngày
│   └── keyword_research.py  # Volume/difficulty/intent + funnel
├── backlinks/
│   └── tracker.py           # Backlink 3 tier + guest post targets
├── profiles/                # (sinh ra khi chạy) cookie/localStorage theo profile
└── reports/                 # (sinh ra khi chạy) CSV xuất từ --export / nút XUẤT CSV
```

## Xử lý sự cố

- **Bị CAPTCHA thường xuyên**: kiểm tra `locale`/`timezone`/`Accept-Language` đã khớp (mặc định đã force `vi-VN`); giữ nguyên file trong `profiles/`; giảm `MAX_SESSIONS_PER_DAY`; cân nhắc dùng proxy VN.
- **Gõ lệnh `python ui.py` báo thiếu module**: chưa `pip install -r requirements.txt` hoặc đang sai môi trường ảo.
- **Playwright không mở được browser**: chạy `playwright install chromium`.
- **Ký tự tiếng Việt hiển thị `?` trong source**: một số file comment bị hỏng encoding (lịch sử lưu ANSI). Chạy `python fix_encoding.py` để sửa các chuỗi quen thuộc, hoặc mở file và lưu lại với encoding UTF-8.

## Giới hạn phụ thuộc

`requirements.txt` gồm: `playwright`, `playwright-stealth`, `customtkinter`, `requests`, `fake-useragent`. `playwright-stealth` là tùy chọn — nếu chưa cài, tool vẫn chạy nhưng bỏ qua lớp stealth bổ sung.
