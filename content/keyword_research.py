"""
content/keyword_research.py — Research từ khóa cho content plan.

Phân tích keyword theo:
- Volume (lượng tìm kiếm)
- Difficulty (độ cạnh tranh)
- Intent (search intent)
- Gợi ý content dựa trên từ khóa
"""
import json
import random

# Mẫu dữ liệu keyword cho ngành làm đẹp mắt
SAMPLE_KEYWORDS = [
    # Head terms (volume cao, cạnh tranh cao)
    {"keyword": "nối mi",              "volume": 14800, "difficulty": 72, "intent": "commercial"},
    {"keyword": "nối mi ở Sài Gòn",    "volume": 9900,  "difficulty": 65, "intent": "commercial"},
    {"keyword": "nối mi ở đâu",          "volume": 8100,  "difficulty": 58, "intent": "commercial"},

    # Body terms (volume TB, intent cao)
    {"keyword": "nối mi tự nhiên giá bao nhiêu", "volume": 3200, "difficulty": 45, "intent": "transactional"},
    {"keyword": "nối mi Hàn Quốc",               "volume": 2900, "difficulty": 48, "intent": "commercial"},
    {"keyword": "uốn mi ở đâu đẹp",                "volume": 2400, "difficulty": 35, "intent": "commercial"},
    {"keyword": "nối mi cho cô dâu",             "volume": 1800, "difficulty": 30, "intent": "transactional"},
    {"keyword": "cách chăm sóc mi nối",          "volume": 1600, "difficulty": 28, "intent": "informational"},
    {"keyword": "nối mi được bao lâu",           "volume": 2200, "difficulty": 32, "intent": "informational"},
    {"keyword": "review nối mi topdev",          "volume": 890,  "difficulty": 12, "intent": "commercial"},

    # Long-tail (volume thấp, intent rất cao)
    {"keyword": "nối mi tự nhiên không hại mi tại salon quận 1", "volume": 420, "difficulty": 8, "intent": "transactional"},
    {"keyword": "địa chỉ nối mi ưng tay gần đây",               "volume": 380, "difficulty": 10, "intent": "commercial"},
    {"keyword": "nối mi cho người mắt một mí 1 mí",            "volume": 320, "difficulty": 15, "intent": "informational"},
    {"keyword": "cách biết nối mi chuẩn hay không chuẩn",      "volume": 280, "difficulty": 10, "intent": "informational"},
]

# Từ khóa định hướng theo funnel (phễu chuyển đổi)
FUNNEL_KEYWORDS = {
    "TOFU (Nhận thức)": [
        "nối mi là gì", "nối mi tự nhiên là gì", "nối mi có tốt không",
        "các loại nối mi", "nối mi Hàn Quốc vs Nhật Bản"
    ],
    "MOFU (Cân nhắc)": [
        "nối mi giá bao nhiêu", "nối mi ở đâu tốt", "nối mi được bao lâu",
        "review nối mi", "cách chọn salon nối mi"
    ],
    "BOFU (Quyết định)": [
        "đặt lịch nối mi", "nối mi tại topdev", "khuyến mãi nối mi",
        "nối mi giá rẻ ở Sài Gòn", "dịch vụ nối mi tại nhà"
    ],
}


def get_keyword_opportunities(min_volume=300, max_difficulty=50):
    """Lấy keyword có cơ hội tốt: volume khá + khó vừa phải."""
    opportunities = [k for k in SAMPLE_KEYWORDS
                     if k["volume"] >= min_volume and k["difficulty"] <= max_difficulty]
    opportunities.sort(key=lambda x: -x["volume"])
    return opportunities


def print_keyword_report():
    """In báo cáo keyword ra console."""
    print("=" * 80)
    print("  KEYWORD RESEARCH REPORT — topdev.vn")
    print("  Ngành: Nối mi, Uốn mi, Làm đẹp mắt")
    print("=" * 80)

    print(f"\n{'Keyword':<40} {'Volume':<10} {'Khó':<6} {'Intent':<15}")
    print("-" * 80)
    for kw in sorted(SAMPLE_KEYWORDS, key=lambda x: -x["volume"]):
        vol_str = f"{kw['volume']:,}"
        print(f"{kw['keyword']:<40} {vol_str:<10} {kw['difficulty']:<6} {kw['intent']:<15}")

    print(f"\n--- Cơ hội tốt (Volume >= 500, Khó <= 50) ---")
    for kw in sorted(get_keyword_opportunities(500, 50), key=lambda x: -x["volume"]):
        vol_str = f"{kw['volume']:,}"
        print(f"  + {kw['keyword']:<38} {vol_str:<10} {kw['difficulty']}/100")

    print(f"\n--- Phễu Content theo Funnel ---")
    for stage, kws in FUNNEL_KEYWORDS.items():
        print(f"  [{stage}]")
        for kw in kws[:3]:
            print(f"    - {kw}")
    print("=" * 80)
