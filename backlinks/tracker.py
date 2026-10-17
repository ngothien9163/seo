"""
backlinks/tracker.py — Quản lý chiến dịch Backlink cho topdev.vn.

Gồm:
- Danh sách backlink mục tiêu (theo ngành làm đẹp)
- Theo dõi trạng thái (đã liên hệ, đã có backlink, bị từ chối)
- Gợi ý chiến dịch guest post, PR, đối tác

CHÚ Ý (F7): `BACKLINK_OPPORTUNITIES` dưới đây là danh sách **cơ hội** — nơi *muốn* đặt
link, `status: "todo"`, URL là homepage của facebook.com/toplist.vn... chứ **không phải
link đã đặt**. Muốn verify link thật ("trang đó còn sống và còn link tới site mình không?")
danh sách nằm ở `config/backlinks.json` (thêm bằng `--backlink-add` / `--backlink-import`
CSV "External links" của Search Console) và chạy `python main.py --backlink-check`
(`utils/backlinks.py` + `utils/backlink_checker.py`). Con số "20 backlink/tháng" của planner
đếm **cơ hội**, không đếm link sống — hai việc khác nhau, đừng đọc lẫn.
"""
from datetime import datetime

# Các loại backlink mục tiêu (theo độ khó)
BACKLINK_OPPORTUNITIES = [
    # Tier 1: Dễ — có trong ngày
    {"source": "Google My Business",           "type": "local",    "difficulty": 1, "status": "todo", "url": "https://business.google.com/"},
    {"source": "Facebook Page",               "type": "social",   "difficulty": 1, "status": "todo", "url": "https://facebook.com/"},
    {"source": "Instagram Business",           "type": "social",   "difficulty": 1, "status": "todo", "url": "https://instagram.com/"},
    {"source": "YouTube Channel",             "type": "video",    "difficulty": 1, "status": "todo", "url": "https://youtube.com/"},
    {"source": "Pinterest",                   "type": "social",   "difficulty": 1, "status": "todo", "url": "https://pinterest.com/"},

    # Tier 2: Trung bình — 1-3 ngày
    {"source": "TopList.vn (ngành làm đẹp)",   "type": "listing",  "difficulty": 2, "status": "todo", "url": "https://toplist.vn/"},
    {"source": "Hỏi đáp LamThep.vn",          "type": "forum",    "difficulty": 2, "status": "todo", "url": "https://lamthep.vn/"},
    {"source": "Webtretho (review dịch vụ)",  "type": "forum",    "difficulty": 2, "status": "todo", "url": "https://webtretho.com/"},
    {"source": "Voice of Youth (review)",      "type": "forum",    "difficulty": 2, "status": "todo", "url": "https://vietnamnet.vn/"},

    # Tier 3: Khó — 1-2 tuần
    {"source": "Guest post trên blog làm đẹp", "type": "guest",    "difficulty": 3, "status": "todo", "url": "Tìm blog beauty VN"},
    {"source": "Hợp tác KOL/influencer",      "type": "pr",       "difficulty": 3, "status": "todo", "url": "Inbox KOL"},
    {"source": "Bài PR trên báo điện tử",      "type": "pr",       "difficulty": 3, "status": "todo", "url": "Webtretho, Eva, Kenh14"},
    {"source": "Đối tác cross-review",        "type": "partner",  "difficulty": 3, "status": "todo", "url": "Salon làm đẹp khác"},
]

# Guest post target (cần liên hệ)
GUEST_POST_TARGETS = [
    {"name": "Blog Làm đẹp",             "domain": "bloglamdep.vn",        "DA": 25, "status": "chưa liên hệ"},
    {"name": "Chia Sẻ đẹp",              "domain": "chiasodep.vn",        "DA": 20, "status": "chưa liên hệ"},
    {"name": "Phụ Nữ Việt",             "domain": "dep365.com",          "DA": 30, "status": "chưa liên hệ"},
    {"name": "Làm đẹp Online",           "domain": "lamdeponline.vn",     "DA": 15, "status": "chưa liên hệ"},
    {"name": "Wiki Làm đẹp",             "domain": "wikilamdep.vn",       "DA": 20, "status": "chưa liên hệ"},
]


def get_tier_summary():
    """Trả về thống kê backlink theo tier."""
    tiers = {"1": 0, "2": 0, "3": 0}
    for bl in BACKLINK_OPPORTUNITIES:
        tier_key = str(bl["difficulty"])
        tiers[tier_key] = tiers.get(tier_key, 0) + 1
    return tiers


def print_backlink_plan():
    """In kế hoạch backlink chi tiết."""
    print("=" * 80)
    print("  BACKLINK STRATEGY — topdev.vn")
    print("  Mục tiêu: 20+ backlink chất lượng trong 30 ngày")
    print("=" * 80)

    tiers = get_tier_summary()
    print(f"\n  Tier 1 (Dễ): {tiers['1']} link — Làm ngay: Google My Business, Facebook, Youtube...")
    print(f"  Tier 2 (TB): {tiers['2']} link — 1-3 ngày: Webtretho, TopList...")
    print(f"  Tier 3 (Khó): {tiers['3']} link — 1-2 tuần: Guest post, KOL, Báo chí")

    print(f"\n--- CHI TIẾT BACKLINK ---")
    print(f"{'#':<3} {'Nguồn':<35} {'Loại':<10} {'Khó':<6} {'Trạng thái'}")
    print("-" * 80)
    for i, bl in enumerate(BACKLINK_OPPORTUNITIES, 1):
        print(f"{i:<3} {bl['source']:<35} {bl['type']:<10} {bl['difficulty']:<6} {bl['status']}")

    print(f"\n--- GUEST POST TARGETS ---")
    print(f"{'#':<3} {'Blog':<20} {'Domain':<25} {'DA':<5} {'Trạng thái'}")
    print("-" * 60)
    for i, gp in enumerate(GUEST_POST_TARGETS, 1):
        print(f"{i:<3} {gp['name']:<20} {gp['domain']:<25} {gp['DA']:<5} {gp['status']}")

    print(f"\n--- TIÊU CHÍ BACKLINK CHẤT LƯỢNG ---")
    print("  - DA (Domain Authority) ≥ 20")
    print("  - Liên quan đến ngành làm đẹp")
    print("  - Không spam site, không link farm")
    print("  - Anchor text tự nhiên: 'dịch vụ nối mi', 'tại topdev'")
    print("  - Đặt từ bài viết blog, không đặt từ footer/sidebar")

    print("=" * 80)
