# config/settings.py — C?u hình SEO toàn di?n

# ────────────────────────────────────────────────────────────────────────────
# PH?N A: CHI?N L??C N?I DUNG (80%)
# ────────────────────────────────────────────────────────────────────────────

# M?c tiêu content hàng tháng
CONTENT_GOAL_MONTHLY = 30          # 30 bài/tháng: blog, video, social, review
CONTENT_FOCUS = "lam dep"          # Ngách chính
TARGET_URL = "https://nankybeauty.com/"   # Website m?c tiêu

# AI Content Generation
CONTENT_MODEL = "qwen3:30b-a3b"    # Model cho sinh content (ho?c "deepseek-chat")

# ────────────────────────────────────────────────────────────────────────────
# PH?N B: CHI?N L??C BACKLINK (D?I V?I AUTOMATION)
# ────────────────────────────────────────────────────────────────────────────

BACKLINK_GOAL_MONTHLY = 20         # 20 backlink/tháng
BACKLINK_MIN_DA = 20               # Minimum Domain Authority

# ────────────────────────────────────────────────────────────────────────────
# PH?N C: T?I ?U K? THU?T & AUTOMATION (20%)
# ────────────────────────────────────────────────────────────────────────────

# Proxy
PROXY_LIST = []

# Browser
HEADLESS_MODE = False
LOAD_IMAGES = True
VIEWPORT_SIZE = {"width": 1920, "height": 1080}

# Device — H? tr? mobile emulation
# M?c d?nh "Random Mobile 70" = 70% mobile, 30% desktop
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

# Android Emulator (ADB) — t?t m?c d?nh, b?t n?u có ?i?n tho?i ?o
ANDROID_EMULATOR_ENABLE = False
ANDROID_EMULATOR_PORT = 5554  # Port m?c d?nh c?a Android Emulator

# Th?i gian on-site (gi?i h?n ?? tránh pattern b?t th??ng)
DURATION_MIN = 45                  # Gi?m xu?ng 45s ?? t? nhiên h?n
DURATION_MAX = 180                 # T?ng lên 180s ?? có phân tán
TEST_DURATION = 60

# Gi?i h?n t?n su?t — TRÁNH B? GOOGLE PHÁT HI?N
MAX_SESSIONS_PER_DAY = 25          # T?i ?a 25 session/ngày (không ph?i 100+)
MIN_INTERVAL_BETWEEN_SESSIONS = 300 # 5 phút gi?a các session

# Loop (ch? b?t khi c?n)
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

# Traffic — t?i ?u t? nhiên, tránh phát hi?n
TRAFFIC_MODE = "search"  # "direct" | "search" | "aio" | "mix"

# Stagger: m?i lu?ng cách nhau 5-20s thay vì kh?i ??ng ?ng lo?t
THREAD_STAGGER_MIN = 5        # Giây t?i thi?u gi?a các lu?ng khi kh?i ??ng
THREAD_STAGGER_MAX = 25

# Ngh? ng?u nhiên gi?a các session trong cùng 1 lu?ng
REST_BETWEEN_SESSIONS_MIN = 10   # Giây
REST_BETWEEN_SESSIONS_MAX = 45

# Gi? l?p gi? cao ?i?m (peak hours)
PEAK_HOURS_ENABLE = True          # Ch?y nhi?u h?n vào gi? cao ?i?m
PEAK_HOURS = [(9, 11), (14, 16), (19, 22)]  # Khung gi? VN
# Danh sách từ khóa KHÔNG nằm ở đây nữa — xem config/keywords.json,
# đọc/ghi qua utils/keywords.py: load_keywords() / save_keywords() / add_keyword().

# AI Engine
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen3:30b-a3b"

# Hành vi nâng cao (gi?m thi?u r?i ro)
POGO_STICK_ENABLE = False          # T?T pogo-stick — nguy c? cao
POGO_STICK_MAX = 0
WARMUP_SEARCH_ENABLE = True        # B?T warmup search — traffic t? search
KEYWORD_VARIATION_ENABLE = True     # B?T keyword variation
THIRD_PAGE_ENABLE = False           # T?T third page — d? b? phát hi?n
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
