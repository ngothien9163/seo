import asyncio
import random
from playwright.async_api import Page
from utils.interactions import human_scroll
from utils.onsite_interactions import rich_on_site_interaction, auto_close_popups
from utils.ai_engine import generate_user_persona
import config.settings as cfg
from utils.keywords import load_keywords

REFERERS = [
    "https://www.google.com.vn/", "https://www.google.com/", "https://www.bing.com/", "https://m.facebook.com/"
]

async def auto_fake_conversion(page: Page):
    """[TẮT] Comment tự động — nguy cơ Google phạt nặng.
    
    Lý do tắt:
    - Google có thể phát hiện comment AI (pattern, thời gian, nội dung)
    - Gây hại cho domain nếu bị phát hiện (penalty mềm ho?c c?ng)
    - T? l? chuy?n ??i t? comment g?n nh? b?ng 0, r?i ro thì cao
    
    Thay vào ?ó: t?p trung content th?t, backlink th?t"""
    pass

async def run_deep_session(page: Page):
    target_url = cfg.TARGET_URL
    total_time_spent = 0
    keywords = load_keywords()
    ai_topic = random.choice(keywords) if keywords else "sản phẩm và dịch vụ nổi bật"
    referer = random.choice(REFERERS) if random.random() < 0.7 else None
    
    try:
        source_name = referer if referer else "Direct (Trực tiếp)"
        print(f"--- [SESSION START] Nguồn: {source_name} ---")
        
        # [NÂNG CẤP BÁ ĐẠO]: Khởi tạo Nhân cách AI cho luồng này
        print("   [🧠] Đang xin cấp phát 'Nhân cách' từ Qwen2.5-Coder...")
        persona = await generate_user_persona(target_url)
        print(f"   [👤] Profile: User {persona['age']} tuổi | Tốc độ gõ: {persona['type_delay_ms']}ms | Tỷ lệ gõ sai: {persona['typo_chance']*100}%")
        
        # Truy cập
        if referer: await page.goto(target_url, referer=referer, wait_until="domcontentloaded", timeout=60000)
        else: await page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
            
        await asyncio.sleep(2)
        await auto_close_popups(page)
        
        # Tương tác phong phú trên site
        await rich_on_site_interaction(page, ai_topic, max_pages=3)

        print(f"--- [SESSION END] Hoàn thành tốt. ---")

    except Exception as e:
        print(f"--- [FAILED] Lỗi Session ngắt quãng: {e} ---")