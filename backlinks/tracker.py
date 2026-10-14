"""
backlinks/tracker.py — Qu?n lý chi?n d?ch Backlink cho topdev.vn.

G?m:
- Danh sách backlink m?c tiêu (theo ngành làm ?p)
- Theo dõi tr?ng thái (dã liên h?, ?ã có backlink, b? t? ch?i)
- G?i ý chi?n d?ch guest post, PR, ??i tác

CHÚ Ý (F7): `BACKLINK_OPPORTUNITIES` dưới đây là danh sách **cơ hội** — nơi *muốn* đặt
link, `status: "todo"`, URL là homepage của facebook.com/toplist.vn... chứ **không phải
link đã đặt**. Muốn verify link thật ("trang đó còn sống và còn link tới site mình không?")
danh sách nằm ở `config/backlinks.json` (thêm bằng `--backlink-add` / `--backlink-import`
CSV "External links" của Search Console) và chạy `python main.py --backlink-check`
(`utils/backlinks.py` + `utils/backlink_checker.py`). Con số "20 backlink/tháng" của planner
đếm **cơ hội**, không đếm link sống — hai việc khác nhau, đừng đọc lẫn.
"""
from datetime import datetime

# Các lo?i backlink m?c tiêu (theo ?? khó)
BACKLINK_OPPORTUNITIES = [
    # Tier 1: D? — có trong ngày
    {"source": "Google My Business",           "type": "local",    "difficulty": 1, "status": "todo", "url": "https://business.google.com/"},
    {"source": "Facebook Page",               "type": "social",   "difficulty": 1, "status": "todo", "url": "https://facebook.com/"},
    {"source": "Instagram Business",           "type": "social",   "difficulty": 1, "status": "todo", "url": "https://instagram.com/"},
    {"source": "YouTube Channel",             "type": "video",    "difficulty": 1, "status": "todo", "url": "https://youtube.com/"},
    {"source": "Pinterest",                   "type": "social",   "difficulty": 1, "status": "todo", "url": "https://pinterest.com/"},

    # Tier 2: Trung bình — 1-3 ngày
    {"source": "TopList.vn (ngành làm ?p)",   "type": "listing",  "difficulty": 2, "status": "todo", "url": "https://toplist.vn/"},
    {"source": "H?i ?áp LamThep.vn",          "type": "forum",    "difficulty": 2, "status": "todo", "url": "https://lamthep.vn/"},
    {"source": "Webtretho (review d?ch v?)",  "type": "forum",    "difficulty": 2, "status": "todo", "url": "https://webtretho.com/"},
    {"source": "Voice of Youth (review)",      "type": "forum",    "difficulty": 2, "status": "todo", "url": "https://vietnamnet.vn/"},

    # Tier 3: Khó — 1-2 tu?n
    {"source": "Guest post trên blog làm ?p", "type": "guest",    "difficulty": 3, "status": "todo", "url": "Tìm blog beauty VN"},
    {"source": "H?p tác KOL/influencer",      "type": "pr",       "difficulty": 3, "status": "todo", "url": "Inbox KOL"},
    {"source": "Bài PR trên báo ??n t?",      "type": "pr",       "difficulty": 3, "status": "todo", "url": "Webtretho, Eva, Kenh14"},
    {"source": "??i tác cross-review",        "type": "partner",  "difficulty": 3, "status": "todo", "url": "Salon làm ?p khác"},
]

# Guest post target (c?n liên h?)
GUEST_POST_TARGETS = [
    {"name": "Blog Làm ?p",             "domain": "bloglamdep.vn",        "DA": 25, "status": "ch?a liên h?"},
    {"name": "Chia S? ?p",              "domain": "chiasodep.vn",        "DA": 20, "status": "ch?a liên h?"},
    {"name": "Ph? N? Vi?t",             "domain": "dep365.com",          "DA": 30, "status": "ch?a liên h?"},
    {"name": "Làm ?p Online",           "domain": "lamdeponline.vn",     "DA": 15, "status": "ch?a liên h?"},
    {"name": "Wiki Làm ?p",             "domain": "wikilamdep.vn",       "DA": 20, "status": "ch?a liên h?"},
]


def get_tier_summary():
    """Tr? v? th?ng kê backlink theo tier."""
    tiers = {"1": 0, "2": 0, "3": 0}
    for bl in BACKLINK_OPPORTUNITIES:
        tier_key = str(bl["difficulty"])
        tiers[tier_key] = tiers.get(tier_key, 0) + 1
    return tiers


def print_backlink_plan():
    """In k? ho?ch backlink chi ti?t."""
    print("=" * 80)
    print("  BACKLINK STRATEGY — topdev.vn")
    print("  M?c tiêu: 20+ backlink ch?t l??ng trong 30 ngày")
    print("=" * 80)

    tiers = get_tier_summary()
    print(f"\n  Tier 1 (D?): {tiers['1']} link — Làm ngay: Google My Business, Facebook, Youtube...")
    print(f"  Tier 2 (TB): {tiers['2']} link — 1-3 ngày: Webtretho, TopList...")
    print(f"  Tier 3 (Khó): {tiers['3']} link — 1-2 tu?n: Guest post, KOL, Báo chí")

    print(f"\n--- CHI TI?T BACKLINK ---")
    print(f"{'#':<3} {'Ngu?n':<35} {'Lo?i':<10} {'Khó':<6} {'Tr?ng thái'}")
    print("-" * 80)
    for i, bl in enumerate(BACKLINK_OPPORTUNITIES, 1):
        print(f"{i:<3} {bl['source']:<35} {bl['type']:<10} {bl['difficulty']:<6} {bl['status']}")

    print(f"\n--- GUEST POST TARGETS ---")
    print(f"{'#':<3} {'Blog':<20} {'Domain':<25} {'DA':<5} {'Tr?ng thái'}")
    print("-" * 60)
    for i, gp in enumerate(GUEST_POST_TARGETS, 1):
        print(f"{i:<3} {gp['name']:<20} {gp['domain']:<25} {gp['DA']:<5} {gp['status']}")

    print(f"\n--- TIÊU CHÍ BACKLINK CH?T L??NG ---")
    print("  - DA (Domain Authority) ≥ 20")
    print("  - Liên quan ??n ngành làm ?p")
    print("  - Không spam site, không link farm")
    print("  - Anchor text t? nhiên: 'd?ch v? n?i mi', 't?i topdev'")
    print("  - ??t t? bài vi?t blog, không ??t t? footer/sidebar")

    print("=" * 80)
