# config/settings.py — Cấu hình SEO toàn diện

# ────────────────────────────────────────────────────────────────────────────
# PHẦN A: CHIẾN LƯỢC NỘI DUNG (80%)
# ────────────────────────────────────────────────────────────────────────────

# Mục tiêu content hàng tháng
CONTENT_GOAL_MONTHLY = 30          # 30 bài/tháng: blog, video, social, review
CONTENT_FOCUS = "lam dep"          # Ngách chính
TARGET_URL = "https://nankybeauty.com/"   # Website mục tiêu

# AI Content Generation
CONTENT_MODEL = "qwen3:30b-a3b"    # Model cho sinh content (hoặc "deepseek-chat")

# ────────────────────────────────────────────────────────────────────────────
# PHẦN B: CHIẾN LƯỢC BACKLINK (ĐỐI VỚI AUTOMATION)
# ────────────────────────────────────────────────────────────────────────────

BACKLINK_GOAL_MONTHLY = 20         # 20 backlink/tháng
BACKLINK_MIN_DA = 20               # Minimum Domain Authority

# ────────────────────────────────────────────────────────────────────────────
# PHẦN C: TỐI ƯU KỸ THUẬT & AUTOMATION (20%)
# ────────────────────────────────────────────────────────────────────────────

# Proxy
PROXY_LIST = []

# Browser
HEADLESS_MODE = False
LOAD_IMAGES = True
VIEWPORT_SIZE = {"width": 1920, "height": 1080}

# Device — Hỗ trợ mobile emulation
# Mặc định "Random Mobile 70" = 70% mobile, 30% desktop
DEVICE_NAME = "Random Mobile 70 (70% mobile, 30% desktop)"
SUPPORTED_DEVICES = [
    "Desktop (Mặc định)",
    "Random (Ngẫu nhiên mọi loại)",
    "Random Mobile (Chỉ điện thoại)",
    "Random Mobile 70 (70% mobile, 30% desktop)",
    "iPhone 14 Pro", "iPhone 14 Pro Max", "iPhone 13 Mini",
    "Pixel 7", "Pixel 5", "Samsung Galaxy S22",
    "iPad Pro 11",
]

# Android Emulator (ADB) — tắt mặc định, bật nếu có điện thoại ảo
ANDROID_EMULATOR_ENABLE = False
ANDROID_EMULATOR_PORT = 5554  # Port mặc định của Android Emulator

# Thời gian on-site (giới hạn để tránh pattern bất thường)
DURATION_MIN = 45                  # Giảm xuống 45s để tự nhiên hơn
DURATION_MAX = 180                 # Tăng lên 180s để có phân tán
TEST_DURATION = 60

# Giới hạn tần suất — TRÁNH BỊ GOOGLE PHÁT HIỆN
MAX_SESSIONS_PER_DAY = 25          # Tối đa 25 session/ngày (không phải 100+)
MIN_INTERVAL_BETWEEN_SESSIONS = 300 # 5 phút giữa các session

# Loop (chỉ bật khi cần)
LOOP_ENABLE = False
LOOP_DURATION_MINUTES = 60
ALWAYS_NEW_USER = True

# Warm-up
WARMUP_ENABLE = True
WARMUP_YOUTUBE = True
WARMUP_NEWS = True
WARMUP_WIKIPEDIA = True
WARMUP_SHOPPING = True
WARMUP_FACEBOOK = True
WARMUP_INSTAGRAM = True

# Traffic — tối ưu tự nhiên, tránh phát hiện
TRAFFIC_MODE = "search"  # "direct" | "search" | "aio" | "mix"

# Stagger: mỗi luồng cách nhau 5-20s thay vì khởi động ồng loạt
THREAD_STAGGER_MIN = 5        # Giây tối thiểu giữa các luồng khi khởi động
THREAD_STAGGER_MAX = 25

# Nghỉ ngẫu nhiên giữa các session trong cùng 1 luồng
REST_BETWEEN_SESSIONS_MIN = 10   # Giây
REST_BETWEEN_SESSIONS_MAX = 45

# Giả lập giờ cao điểm (peak hours)
PEAK_HOURS_ENABLE = True          # Chạy nhiều hơn vào giờ cao điểm
PEAK_HOURS = [(9, 11), (14, 16), (19, 22)]  # Khung giờ VN
# Danh sách từ khóa KHÔNG nằm ở đây nữa — xem config/keywords.json,
# đọc/ghi qua utils/keywords.py: load_keywords() / save_keywords() / add_keyword().

# AI Engine
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen3:30b-a3b"

# Model nhỏ, nhanh dùng riêng cho bước chọn link ngữ nghĩa (khác model sinh content)
SEMANTIC_LINK_MODEL = "qwen2.5-coder:7b"

# Gỡ lỗi tầng giả lập hành vi: True → in lý do mỗi `except` bắt được (xem utils/dbg.py)
INTERACTION_DEBUG = False

# Hành vi nâng cao (giảm thiểu rủi ro)
POGO_STICK_ENABLE = False          # TẮT pogo-stick — nguy cơ cao
POGO_STICK_MAX = 0
WARMUP_SEARCH_ENABLE = True        # BẬT warmup search — traffic từ search
KEYWORD_VARIATION_ENABLE = True     # BẬT keyword variation
THIRD_PAGE_ENABLE = False           # TẮT third page — dễ bị phát hiện
THIRD_PAGE_CHANCE = 0

# ────────────────────────────────────────────────────────────────────────────
# PHẦN D: RANK TRACKING — theo dõi vị trí từ khóa trên Google
# ────────────────────────────────────────────────────────────────────────────
RANK_CHECK_DEPTH = 100            # Tìm domain trong top N kết quả (num=100)
RANK_CHECK_MAX_PER_DAY = 3        # Số lần check đầy đủ tối đa mỗi ngày
RANK_CHECK_MIN_INTERVAL = 3600    # Giây tối thiểu giữa 2 lần check
RANK_KEYWORD_DELAY_MIN = 8        # Giây nghỉ giữa 2 từ khóa (giả lập người)
RANK_KEYWORD_DELAY_MAX = 20

# ────────────────────────────────────────────────────────────────────────────
# PHẦN E: GOOGLE SEARCH CONSOLE — dữ liệu SEO thật qua API (không scrape)
# ────────────────────────────────────────────────────────────────────────────
GSC_SITE_URL = "sc-domain:nankybeauty.com"  # Property URL (sc-domain:... hoặc https://...)
GSC_CREDENTIALS_FILE = "config/gsc_service_account.json"  # JSON key service account (docs/SETUP_GSC.md)
GSC_LOOKBACK_DAYS = 28            # Lấy dữ liệu 28 ngày gần nhất
GSC_MAX_FETCH_PER_DAY = 4         # Số lần fetch tối đa/ngày (quota API 1200/phút — chỉ để tránh gọi thừa)

# F2 — biến query GSC thành từ khóa cần theo dõi
KEYWORD_SUGGEST_MIN_IMPRESSIONS = 30   # Ngưỡng impressions (inclusive) để một query được đề xuất
KEYWORD_SUGGEST_LIMIT = 20             # Số đề xuất hiển thị tối đa mỗi lần (--gsc-keywords / GUI)

# ────────────────────────────────────────────────────────────────────────────
# PHẦN F: CẢNH BÁO TỤT HẠNG (F3) — Telegram, mặc định TẮT
# ────────────────────────────────────────────────────────────────────────────
ALERTS_ENABLE = False             # Bật = gửi Telegram; Tắt = rules vẫn chạy, chỉ in console
RANK_ALERT_DROP = 5               # Báo khi hạng rơi >= N vị trí so với lần check liền trước
RANK_ALERT_TOP10_FALL = True      # Báo khi từ khóa đang trong Top 10 bị rớt ra ngoài
TELEGRAM_BOT_TOKEN = ""           # Token từ @BotFather — xem docs/SETUP_ALERTS.md
TELEGRAM_CHAT_ID = ""             # Chat id nhận tin (cá nhân hoặc nhóm)
ALERTS_STATE_DIR = "data"         # Thư mục state chống spam (1 tin/ngày/từ khóa)
# C4 — cảnh báo xu hướng: nhìn chuỗi check dài, dự báo rớt TRƯỚC khi rớt thật.
# So trung bình hạng của 4 mốc mới nhất với 4 mốc ngay trước đó (trong window
# lần check gần nhất) — trung bình xấu đi từ RANK_ALERT_TREND_DROP vị trí là
# "đang giảm dần" → cảnh báo sớm, trước khi chạm ngưỡng tụt đột ngột.
RANK_ALERT_TREND_ENABLE = True    # Bật rule xu hướng; tắt thì vẫn còn rule tụt đột ngột
RANK_ALERT_TREND_DROP = 3         # Số vị trí xấu đi (trung bình) coi là "giảm dần"
RANK_ALERT_TREND_WINDOW = 14      # Số lần check gần nhất được nhìn (cũ hơn bỏ qua)

# ────────────────────────────────────────────────────────────────────────────
# PHẦN G: LỊCH TỰ ĐỘNG (F4) — đồng hồ thật là Windows Task Scheduler
# ────────────────────────────────────────────────────────────────────────────
# Các giờ dưới đây là LỊCH MONG MUỐN: chỉ để đăng ký task (docs/SETUP_SCHEDULER.md)
# và in ra khi xem --scheduler-status. Code không tự thức dậy; máy tắt đúng giờ thì
# không chạy bù (quyết định đã duyệt trong spec F4).
SCHEDULER_RANK_HOURS = [7, 13, 19]   # giờ trong ngày check thứ hạng từ khóa
SCHEDULER_GSC_HOURS = [9]            # giờ kéo dữ liệu Search Console
SCHEDULER_BACKLINK_HOURS = []        # giờ verify backlink — rỗng = chỉ chạy tay [--run-job backlink]
SCHEDULER_TRAFFIC_ENABLE = False     # traffic tự chạy = quyết định của owner, mặc định TẮT
SCHEDULER_NOTIFY_ENABLE = False      # tin Telegram tóm tắt sau mỗi job — bật cùng ALERTS_ENABLE
SCHEDULER_LOCK_STALE = 1200          # giây không heartbeat là lock bị coi đã chết (20 phút)

# ────────────────────────────────────────────────────────────────────────────
# PHẦN H: AUDIT ON-PAGE (F6) — --audit crawl chính site của mình, không đụng trình duyệt
# ────────────────────────────────────────────────────────────────────────────
AUDIT_MAX_PAGES = 100               # Số trang tối đa mỗi lần --audit (--audit-limit N để đổi)
AUDIT_TIMEOUT = 10                  # giây/request — link hỏng không được treo cả đợt audit
# UA desktop tĩnh để request HTML. Crawler không phải Googlebot và không đánh cược
# với bot-detection: chỉ lấy HTML tĩnh của site mình, không đụng lớp anti-detect.
AUDIT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
AUDIT_STATE_DIR = "data"            # nơi lưu audit_last.json — kết quả lần audit gần nhất để --export audit đọc lại
PAGESPEED_TIMEOUT = 90              # giây/lượt — PSI tự chạy Lighthouse, chậm hơn crawl rất nhiều
PAGESPEED_STATE_DIR = "data"        # nơi lưu pagespeed.json (chỉ số gọn, không chứa response thô)
# PSI không key dùng chung một quota "Queries per day" toàn cầu — đã đo 2026-10-14: hết là hết.
# Điền key miễn phí (Google Cloud Console -> PageSpeed Insights API) để thoát cảnh đó; để trống vẫn chạy.
PAGESPEED_API_KEY = ""

# ────────────────────────────────────────────────────────────────────────────
# PHẦN I: BACKLINK AUTO-CHECK (F7) — verify link đã đặt, lịch sự với site người khác
# ────────────────────────────────────────────────────────────────────────────
BACKLINK_PARALLEL = 5               # luồng fetch song song — nhiều hơn là gây tải cho host lạ
BACKLINK_TIMEOUT = 15               # giây/link — một trang treo không được kéo cả batch
BACKLINK_CACHE_HOURS = 24           # link vừa check trong vòng này không fetch lại (như snapshot GSC)
BACKLINK_STATE_DIR = "data"         # nơi lưu backlink_status.json (kết quả check — gitignored)
BACKLINK_STORE_FILE = "backlinks.json"  # nằm trong config/, danh sách link owner tự thêm

# ────────────────────────────────────────────────────────────────────────────
# PHẦN J: CONTENT GENERATION (F8) — chỉ nói chuyện với Ollama localhost, chỉ sinh draft
# ────────────────────────────────────────────────────────────────────────────
CONTENT_GEN_TIMEOUT = 300           # giây/lượt — model 30b chậm, bản nháp dài cần nhiều thời gian
CONTENT_GEN_RETRIES = 1             # chỉ retry khi timeout; connection error không retry
CONTENT_DRAFTS_DIR = "content/drafts"  # nơi lưu bài nháp .md (gitignored — owner duyệt rồi mới dùng)

# ────────────────────────────────────────────────────────────────────────────
# PHẦN K: AEO TRACKING (F9) — hỏi AI engine theo từ khóa, dán tay câu trả lời
# ────────────────────────────────────────────────────────────────────────────
# Hướng đã chốt trong roadmap: KHÔNG tự hỏi AI bằng browser (lớp anti-detect bị
# loại) — người dùng gặp AI thường ngày, copy câu trả lời vào file rồi chạy
# --aeo-check; công cụ chỉ phân tích text, KHÔNG gửi request nào.
AEO_BRANDS = ["Nanky Beauty", "nankybeauty.com", "nanky beauty"]  # biến thể brand cần nhận ra
AEO_HISTORY_KEEP = 500            # số bản ghi tối đa — cũ nhất bị cắt (theo ngày dán)

# ────────────────────────────────────────────────────────────────────────────
# PHẦN L: WORDPRESS DRAFT (C1) — tool chỉ đẩy bài NHÁP, owner duyệt rồi publish
# ────────────────────────────────────────────────────────────────────────────
# App Password tạo trong WP admin (Users → Profile → Application Passwords);
# đây KHÔNG phải mật khẩu đăng nhập — dùng riêng cho tool, dễ thu hồi.
WP_URL = ""                       # VD "https://nankybeauty.com" — không có /wp-json
WP_USER = ""                      # username trong WP (không phải email nếu WP yêu cầu)
WP_APP_PASSWORD = ""              # App Password — nên để biến môi trường WP_APP_PASSWORD (thắng settings, không commit)
WP_DEFAULT_CATEGORIES = []        # TÊN category gán mặc định khi đẩy nháp (VD ["Tin tức"]) — owner tự chọn
WP_DEFAULT_TAGS = []              # TÊN tag mặc định — tool tra id; term chưa có trên WP bị bỏ qua + cảnh báo, KHÔNG tạo mới

