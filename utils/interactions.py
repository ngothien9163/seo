import asyncio
import random
import requests
import re
from playwright.async_api import Page
from utils.mouse_helper import human_move
from utils import dbg
import config.settings as cfg

async def random_sleep(min_s=1.0, max_s=3.0):
    await asyncio.sleep(random.uniform(min_s, max_s))

# [NÂNG CẤP]: Bổ sung hàm gõ phím giả lập người thật
async def human_typing(page: Page, selector: str, text: str):
    """Gõ phím với tốc độ không đều và thỉnh thoảng gõ sai"""
    print(f"   [✍️] Đang gõ văn bản: '{text}'")
    await page.click(selector)
    await asyncio.sleep(0.5)

    for char in text:
        # 5% cơ hội gõ nhầm một phím rồi phải xóa
        if random.random() < 0.05:
            wrong_char = random.choice('abcdefghijklmnopqrstuvwxyz')
            await page.type(selector, wrong_char, delay=random.randint(50, 150))
            await asyncio.sleep(0.3)
            await page.keyboard.press('Backspace')
            await asyncio.sleep(0.2)
        
        # Gõ phím thật với delay ngẫu nhiên từng ký tự
        delay = random.randint(30, 180)
        await page.type(selector, char, delay=delay)

async def human_scroll(page: Page, duration: int):
    """Cuộn trang kết hợp đọc, rung chuột và bôi đen"""
    print(f"   [*] 📖 Đang đọc & tương tác ({duration}s)...")
    loop = asyncio.get_running_loop()
    start_time = loop.time()
    
    while loop.time() - start_time < duration:
        # Cuộn xuống
        await page.mouse.wheel(0, random.randint(150, 400))
        
        # Random hành vi phụ
        dice = random.random()
        if dice < 0.15:
            await random_mouse_jitter(page)
        elif dice < 0.25:
            await random_highlight_text(page)
        elif dice < 0.35: # Cuộn ngược lên (xem lại)
            await page.mouse.wheel(0, -random.randint(100, 300))

        await asyncio.sleep(random.uniform(1.5, 4.0))

async def random_mouse_jitter(page: Page):
    """Rung lắc chuột nhẹ"""
    try:
        x, y = random.randint(300, 1000), random.randint(300, 800)
        await human_move(page, x, y)
        for _ in range(random.randint(3, 5)):
            await page.mouse.move(x + random.randint(-10, 10), y + random.randint(-10, 10))
            await asyncio.sleep(0.05)
    except Exception as e:
        dbg.warn("random_mouse_jitter", e)

async def random_highlight_text(page: Page):
    """Bôi đen văn bản"""
    try:
        paragraphs = await page.locator("p, span").all()
        if not paragraphs: return
        
        target = random.choice(paragraphs)
        if await target.is_visible():
            box = await target.bounding_box()
            if box:
                await human_move(page, box['x'], box['y'])
                await asyncio.sleep(0.3)
                
                await page.mouse.down()
                await human_move(page, box['x'] + random.randint(50, 200), box['y'] + 10)
                await page.mouse.up()
                
                await asyncio.sleep(1.0)
                await page.mouse.click(box['x'] - 20, box['y'])
    except Exception as e:
        dbg.warn("random_highlight_text", e)

async def click_random_internal_link(page: Page):
    """Click link nội bộ an toàn"""
    try:
        current_url = page.url
        domain_parts = current_url.split("/")
        if len(domain_parts) < 3: return False
        base_domain = domain_parts[2]

        selector = f"a[href*='{base_domain}'], a[href^='/']"
        links = await page.locator(selector).all()
        
        valid_links = [l for l in links if await l.is_visible()]
        
        if valid_links:
            target = random.choice(valid_links)
            txt = await target.inner_text()
            
            await target.scroll_into_view_if_needed()
            await random_sleep(0.5, 1.0)
            
            box = await target.bounding_box()
            if box:
                center_x = box['x'] + box['width']/2 + random.randint(-5, 5)
                center_y = box['y'] + box['height']/2 + random.randint(-5, 5)
                await human_move(page, center_x, center_y)
                
                await asyncio.sleep(random.uniform(0.2, 0.5))
                await target.click(force=True)
                print(f"   [+] 👆 Click: {txt.strip()[:20]}...")
                return True
        return False
    except Exception:
        return False


async def get_semantic_link_choice(current_keyword: str, links_data: list) -> int:
    """Gọi Ollama (cfg.SEMANTIC_LINK_MODEL) để chọn link ngữ nghĩa theo từ khóa."""
    url = cfg.OLLAMA_URL
    
    # Format danh sách link cho AI dễ đọc
    links_text = "\n".join([f"[{i}] {link['text']}" for i, link in enumerate(links_data)])
    
    prompt = f"""Bạn là một người dùng đang tìm hiểu về chủ đề '{current_keyword}'.
Dưới đây là danh sách các link trên trang web hiện hành:
{links_text}

Nhiệm vụ: Chọn MỘT link hấp dẫn và liên quan nhất để click đọc tiếp. Ưu tiên các bài viết, dịch vụ hoặc bảng giá. Tránh các trang vô nghĩa như 'Trang chủ', 'Đăng nhập', 'Giỏ hàng'.
YÊU CẦU BẮT BUỘC: Chỉ trả về ĐÚNG MỘT CON SỐ tương ứng với ID của link trong ngoặc vuông. KHÔNG GIẢI THÍCH GÌ THÊM."""

    payload = {
        "model": cfg.SEMANTIC_LINK_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1 # Nhiệt độ cực thấp để model trả lời chính xác như 1 cỗ máy
        }
    }
    
    try:
        # Chạy request trong luồng riêng (to_thread) để không làm treo giao diện UI
        response = await asyncio.to_thread(requests.post, url, json=payload, timeout=30)
        result_text = response.json().get("response", "").strip()
        
        # Dùng Regex để lọc lấy chính xác con số ID AI chọn (VD: AI trả lời "[3]" hoặc "3" -> Lấy số 3)
        numbers = re.findall(r'\d+', result_text)
        if numbers:
            return int(numbers[0])
        return -1
    except Exception as e:
        print(f"   [⚠️] Lỗi gọi Ollama API: {e}")
        return -1

async def click_semantic_internal_link(page: Page, keyword: str):
    """Thay thế click_random bằng AI-driven click"""
    try:
        current_url = page.url
        domain_parts = current_url.split("/")
        if len(domain_parts) < 3: return False
        base_domain = domain_parts[2]

        # Lấy tất cả các thẻ <a> nội bộ
        selector = f"a[href*='{base_domain}'], a[href^='/']"
        links = await page.locator(selector).all()
        
        valid_links = []
        for l in links:
            if await l.is_visible():
                txt = await l.inner_text()
                href = await l.get_attribute("href")
                # Chỉ lấy các link có text rõ ràng, độ dài > 3 ký tự để gửi cho AI
                if txt and len(txt.strip()) > 3:
                    valid_links.append({"element": l, "text": txt.strip(), "href": href})
        
        if not valid_links: return False

        # Lấy ngẫu nhiên tối đa 15 link để gửi cho AI (Tránh nhồi nhét quá nhiều làm AI quá tải)
        sample_links = random.sample(valid_links, min(len(valid_links), 15))

        print(f"   [🧠] Đang hỏi Qwen2.5-Coder phân tích link phù hợp với '{keyword}'...")
        chosen_index = await get_semantic_link_choice(keyword, sample_links)

        if 0 <= chosen_index < len(sample_links):
            target_data = sample_links[chosen_index]
            print(f"   [🧠] AI quyết định chọn Link ID [{chosen_index}]!")
        else:
            print("   [🧠] AI phân vân, tự động dự phòng sang link ngẫu nhiên.")
            target_data = random.choice(sample_links)

        target = target_data["element"]
        txt = target_data["text"]

        await target.scroll_into_view_if_needed()
        await asyncio.sleep(random.uniform(0.5, 1.0))
        
        box = await target.bounding_box()
        if box:
            center_x = box['x'] + box['width']/2 + random.randint(-5, 5)
            center_y = box['y'] + box['height']/2 + random.randint(-5, 5)
            await human_move(page, center_x, center_y)
            
            await asyncio.sleep(random.uniform(0.2, 0.5))
            await target.click(force=True)
            display_txt = txt[:40].replace('\n', ' ')
            print(f"   [+] 👆 Click Ngữ Nghĩa: {display_txt}...")
            return True
            
        return False
    except Exception as e:
        print(f"   [-] Lỗi Semantic Click: {e}")
        return False