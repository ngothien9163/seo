"""
content/planner.py — Sinh chiến lược Content SEO tổng thể.

Công cụ này giúp tạo ra một lịch trình content cấu trúc, tối ưu theo keyword,
tăng authority cho topdev.vn — thay vì chỉ dựa vào automation.

Dùng AI (Ollama hoặc DeepSeek) để phân tích ngách và đề xuất nội dung.
"""
import json
import os
from datetime import datetime, timedelta

# Cấu hình — ưu tiên dùng DeepSeek nếu có
CONTENT_MODEL = "qwen3:30b-a3b"  # hoặc "deepseek-chat"
CONTENT_TIMEOUT = 120

# Mẫu lịch content 30 ngày cho ngành làm đẹp (nối mi, uốn mi)
DEFAULT_30D_PLAN = [
    # Tuần 1: Giới thiệu & Giáo dục
    {"day": 1,  "type": "blog",   "keyword": "nối mi tự nhiên là gì", "target": "Giải thích khái niệm, ai nên làm"},
    {"day": 2,  "type": "blog",   "keyword": "các loại nối mi phổ biến", "target": "So sánh 5-7 loại nối mi"},
    {"day": 3,  "type": "social", "keyword": "nối mi được bao lâu", "target": "Infographic về độ bền nối mi"},
    {"day": 4,  "type": "blog",   "keyword": "nối mi có hại mi không", "target": "Giải đáp lo lắng thường gặp"},
    {"day": 5,  "type": "video",  "keyword": "quy trình nối mi tại salon", "target": "Behind-the-scenes 60s TikTok"},
    {"day": 6,  "type": "blog",   "keyword": "cách chọn salon nối mi uy tín", "target": "Checklist cho khách hàng mới"},
    {"day": 7,  "type": "review", "keyword": "review dịch vụ nối mi tại topdev", "target": "Tổng hợp cảm nhận khách hàng thật"},

    # Tuần 2: Chuyên sâu & So sánh
    {"day": 8,  "type": "blog",   "keyword": "nối mi Hàn Quốc vs Nhật Bản", "target": "So sánh chi tiết 2 trường phái"},
    {"day": 9,  "type": "blog",   "keyword": "chăm sóc mi sau khi nối", "target": "Hướng dẫn chăm sóc 7 ngày"},
    {"day": 10, "type": "social", "keyword": "trước và sau khi nối mi", "target": "Before/After gallery"},
    {"day": 11, "type": "blog",   "keyword": "nối mi giá bao nhiêu", "target": "Bảng giá chi tiết + yếu tố ảnh hưởng"},
    {"day": 12, "type": "video",  "keyword": "hướng dẫn tự trang điểm mi tại nhà", "target": "Tutorial 90s cho khách"},
    {"day": 13, "type": "blog",   "keyword": "uốn mi là gì có tốt không", "target": "So sánh uốn mi vs nối mi"},
    {"day": 14, "type": "review", "keyword": "khách hàng nổi tiếng dùng dịch vụ", "target": "Case study: khách hàng thật"},

    # Tuần 3: Mở rộng & Tạo authority
    {"day": 15, "type": "blog",   "keyword": "dịch vụ làm đẹp mắt trọn gói", "target": "Gói combo: mi + mày + mặt"},
    {"day": 16, "type": "blog",   "keyword": "phong cách làm đẹp Hàn Quốc hot 2026", "target": "Xu hướng làm đẹp Hàn Quốc"},
    {"day": 17, "type": "social", "keyword": "học nối mi ở đâu", "target": "Giới thiệu khóa học tại topdev"},
    {"day": 18, "type": "blog",   "keyword": "dịch vụ nối mi cho cô dâu", "target": "Gói cưới trọn gói"},
    {"day": 19, "type": "blog",   "keyword": "cách nhận biết nối mi chất lượng", "target": "Hướng dẫn cho người mới"},
    {"day": 20, "type": "video",  "keyword": "phỏng vấn chuyên viên nối mi", "target": "Expert interview 3-5 phút"},
    {"day": 21, "type": "blog",   "keyword": "dịch vụ làm đẹp tại topdev có gì hot", "target": "Tổng quan về dịch vụ"},

    # Tuần 4: Tối ưu chuyển đổi & Kêu gọi hành động
    {"day": 22, "type": "blog",   "keyword": "địa chỉ nối mi ưng tay ở Sài Gòn", "target": "Local SEO + Google Maps"},
    {"day": 23, "type": "social", "keyword": "khuyến mãi nối mi tháng này", "target": "Promotion post + link đặt lịch"},
    {"day": 24, "type": "blog",   "keyword": "các lưu ý khi đi nối mi lần đầu", "target": "Checklist cho newbie"},
    {"day": 25, "type": "blog",   "keyword": "nối mi cho mắt một mí", "target": "Kỹ thuật nối mi cho từng dạng mắt"},
    {"day": 26, "type": "blog",   "keyword": "câu hỏi thường gặp về nối mi", "target": "FAQ Schema cho Google"},
    {"day": 27, "type": "video",  "keyword": "khách hàng nói gì về topdev", "target": "Testimonial compilation"},
    {"day": 28, "type": "blog",   "keyword": "lịch sử phát triển ngành nối mi", "target": "Bài dài tạo authority"},
    {"day": 29, "type": "blog",   "keyword": "so sánh các salon nối mi tại VN", "target": "So sánh có đối chiếu topdev"},
    {"day": 30, "type": "review", "keyword": "tổng kết tháng: kết quả khách hàng", "target": "Monthly roundup + CTA booking"},
]

def get_plan_summary():
    """Trả về bảng tổng kết lịch content 30 ngày."""
    blogs = sum(1 for p in DEFAULT_30D_PLAN if p["type"] == "blog")
    videos = sum(1 for p in DEFAULT_30D_PLAN if p["type"] == "video")
    socials = sum(1 for p in DEFAULT_30D_PLAN if p["type"] == "social")
    reviews = sum(1 for p in DEFAULT_30D_PLAN if p["type"] == "review")

    return {
        "total": 30,
        "blogs": blogs,
        "videos": videos,
        "socials": socials,
        "reviews": reviews,
        "cost_estimate": f"Ước tính: {blogs}x ~15 giờ viết + {videos}x ~2 giờ edit + {socials}x ~1 giờ design"
    }

def print_plan():
    """In lịch content ra console — heading theo site hiện tại, không brand chết."""
    from utils.site_paths import site_domain
    print("=" * 80)
    print(f"  CONTENT STRATEGY — 30 NGÀY CHO {site_domain().upper() or 'SITE CỦA BẠN'}")
    print("  Mục tiêu: Xây dựng authority tự nhiên, giảm phụ thuộc automation")
    print("=" * 80)
    print(f"{'Ngày':<6} {'Loại':<8} {'Keyword':<35} {'Mục tiêu'}")
    print("-" * 80)
    for item in DEFAULT_30D_PLAN:
        print(f"{item['day']:<6} {item['type']:<8} {item['keyword']:<35} {item['target']}")
    print("-" * 80)
    summary = get_plan_summary()
    print(f"Tổng: {summary['total']} bài | Blog: {summary['blogs']} | Video: {summary['videos']} | Social: {summary['socials']} | Review: {summary['reviews']}")
    print(summary['cost_estimate'])
    print("=" * 80)
