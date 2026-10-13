import asyncio
import random
import re
from urllib.parse import unquote
from playwright.async_api import Page

from utils.interactions import human_scroll
from utils.onsite_interactions import rich_on_site_interaction, auto_close_popups
from utils.ai_engine import (
    generate_user_persona,
    generate_search_behavior,
    generate_related_keyword,
    PersonaConfig,
)
import config.settings as cfg
from utils.keywords import load_keywords


# ─── warm-up sites phân loại theo persona ────────────────────────────────────

_WARMUP_FEMALE = [
    "https://eva.vn",
    "https://kenh14.vn",
    "https://phunuvietnam.vn",
    "https://elle.vn/lam-dep",
    "https://soha.vn",
]
_WARMUP_GENERAL = [
    "https://vnexpress.net",
    "https://dantri.com.vn",
    "https://tuoitre.vn",
    "https://thanhnien.vn",
    "https://24h.com.vn",
]


# ─── helpers: trước khi vào Google ───────────────────────────────────────────

async def _warmup_before_search(page: Page, persona: PersonaConfig):
    """
    Ghé trang VN phù hợp với persona trước Google — tạo lịch sử duyệt tự nhiên.
    Xác suất warmup: hurried=20%, curious=50%, relaxed=65%.
    Site chọn theo gender: female → beauty/lifestyle, male → news.
    Có thể tắt hoàn toàn bằng cfg.WARMUP_SEARCH_ENABLE = False.
    """
    if not getattr(cfg, "WARMUP_SEARCH_ENABLE", True):
        return
    mood = persona.get("mood", "relaxed")
    warmup_prob = {"hurried": 0.20, "curious": 0.50, "relaxed": 0.65}.get(mood, 0.35)
    if random.random() > warmup_prob:
        return

    sites = _WARMUP_FEMALE if persona.get("gender") == "female" else _WARMUP_GENERAL
    site = random.choice(sites)
    print(f"   [🌐] Warm-up: Ghé qua {site} trước khi tìm kiếm...")
    try:
        await page.goto(site, wait_until="domcontentloaded", timeout=30000)
        await auto_close_popups(page)
        dwell_ranges = {"hurried": (8, 15), "curious": (20, 35), "relaxed": (25, 45)}
        dwell = random.randint(*dwell_ranges.get(mood, (12, 25)))
        elapsed = 0.0
        while elapsed < dwell:
            await page.mouse.wheel(0, random.randint(150, 400))
            pause = random.uniform(1.5, 4.0)
            await asyncio.sleep(pause)
            elapsed += pause
        print(f"   [🌐] Xong warm-up ({dwell}s). Chuyển sang Google...")
        await asyncio.sleep(random.uniform(1.0, 2.0))
    except Exception as e:
        print(f"   [-] Bỏ qua warm-up: {e}")


# ─── helpers: Google SERP ────────────────────────────────────────────────────

async def _accept_google_consent(page: Page):
    """Chấp nhận popup cookie/đồng ý của Google (nhiều biến thể UI)."""
    for sel in (
        "button#L2AGLb",
        "button#CXQnmb",
        "button[aria-label*='Accept']",
        "button[aria-label*='Đồng ý']",
        "form[action*='consent'] button",
    ):
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=1500):
                await btn.click()
                await asyncio.sleep(1.5)
                return
        except Exception:
            pass


def _is_captcha(page: Page) -> bool:
    """Kiem tra CAPTCHA ca tren URL va DOM elements."""
    # Kiem tra URL
    url = page.url
    if any(k in url for k in ("/sorry/", "sorry/index", "recaptcha", "captcha")):
        return True
    # Kiem tra element tren trang (JS CAPTCHA popup khong doi URL)
    try:
        captcha_selectors = [
            "iframe[src*='recaptcha']", "div[class*='g-recaptcha']",
            "div[class*='captcha']", "#captcha", "[aria-label*='captcha']",
        ]
        for sel in captcha_selectors:
            el = page.locator(sel).first
            if el and el.is_visible(timeout=500):
                return True
    except Exception:
        pass
    return False


def _unwrap_google_redirect(href: str) -> str:
    """Google đôi khi bọc URL trong /url?q=... — bóc tách URL thật."""
    if "/url?q=" in href:
        m = re.search(r"/url\?q=([^&]+)", href)
        if m:
            return unquote(m.group(1))
    return href


async def _find_target_on_serp(page: Page, domain_target: str):
    """
    Quét SERP bằng selector chính xác, xử lý Google redirect URL.
    Trả về (element, real_href) hoặc (None, None).
    """
    selector_chain = [
        f"#search a[href*='{domain_target}']:not([href*='google'])",
        f"#rso a[href*='{domain_target}']",
        f"#search a[href*='/url?q=']",
        f"a[href*='{domain_target}']:not([href*='google.com'])",
    ]
    for sel in selector_chain:
        try:
            for link in await page.locator(sel).all():
                href = await link.get_attribute("href")
                if not href:
                    continue
                real_href = _unwrap_google_redirect(href)
                if domain_target in real_href and "google.com" not in real_href:
                    if await link.is_visible():
                        return link, real_href
        except Exception:
            continue
    return None, None


async def _find_competitor_links(page: Page, domain_target: str, count: int) -> list:
    """
    Tìm N kết quả đối thủ trên SERP — loại trừ site mình, Google, YouTube, Wikipedia.
    Mỗi domain chỉ lấy 1 link để tránh click nhiều lần cùng đối thủ.
    """
    _exclude = (
        "google.com", "google.com.vn", domain_target,
        "youtube.com", "wikipedia.org", "maps.google", "translate.google",
    )
    results, seen_domains = [], set()
    try:
        links = await page.locator("#search a[href^='http'], #rso a[href^='http']").all()
        for link in links:
            if len(results) >= count:
                break
            try:
                href = await link.get_attribute("href")
                if not href or not href.startswith("http"):
                    continue
                if any(ex in href for ex in _exclude):
                    continue
                link_domain = href.split("/")[2]
                if link_domain in seen_domains:
                    continue
                txt = await link.inner_text()
                if not txt or len(txt.strip()) < 5:
                    continue
                if await link.is_visible():
                    seen_domains.add(link_domain)
                    results.append((link, href))
            except Exception:
                continue
    except Exception:
        pass
    return results


async def _click_competitors_with_pogo(
    page: Page, domain_target: str, persona: PersonaConfig, count: int
):
    """
    Click N trang đối thủ với dwell ngắn rồi bấm Back — pogo-sticking signal.
    Gửi tín hiệu cho Google: trang đối thủ không thỏa mãn người dùng.
    Dwell ngắn (13-27s) + scroll nhẹ = không bị bot-detect nhưng vẫn pogo.
    """
    if count <= 0:
        return
    competitors = await _find_competitor_links(page, domain_target, count)
    if not competitors:
        print("   [-] Không tìm thấy kết quả đối thủ để pogo-stick.")
        return

    for i, (link, href) in enumerate(competitors):
        domain_short = href.split("/")[2][:35] if "/" in href else href[:35]
        print(f"   [🔀] Pogo-stick đối thủ {i+1}/{len(competitors)}: {domain_short}...")
        try:
            await link.scroll_into_view_if_needed()
            await asyncio.sleep(random.uniform(0.8, 1.8))
            await link.click()
            await page.wait_for_load_state("domcontentloaded", timeout=20000)

            # Dwell theo mood: curious ở lâu hơn chút, hurried thoát nhanh hơn
            mood = persona.get("mood", "relaxed")
            dwell_s = {"hurried": random.randint(10, 18), "curious": random.randint(20, 30)}.get(mood, random.randint(13, 25))
            scroll_count = random.randint(2, 4)
            print(f"   [⏱️] Đọc lướt {dwell_s}s rồi bấm Back...")
            for _ in range(scroll_count):
                await page.mouse.wheel(0, random.randint(80, 280))
                await asyncio.sleep(dwell_s / scroll_count + random.uniform(-0.5, 0.8))

            await page.go_back(wait_until="domcontentloaded", timeout=20000)
            # Scroll nhẹ để re-orient trên SERP sau khi back
            await asyncio.sleep(random.uniform(1.2, 2.5))
            await page.mouse.wheel(0, random.randint(-60, 100))
            await asyncio.sleep(random.uniform(0.8, 1.5))

        except Exception as e:
            print(f"   [-] Lỗi pogo-stick: {e}")
            try:
                await page.go_back(wait_until="domcontentloaded", timeout=10000)
                await asyncio.sleep(1.5)
            except Exception:
                pass


async def _simulate_reading_snippet(page: Page, link_el, duration_s: float):
    """Di chuột vào vùng snippet (dưới title) như người đang đọc mô tả kết quả."""
    try:
        from utils.mouse_helper import human_move
        box = await link_el.bounding_box()
        if box:
            await human_move(page, box["x"] + box["width"] / 2, box["y"] + box["height"] + 22)
    except Exception:
        pass
    await asyncio.sleep(duration_s)


async def _locate_and_click_target(
    page: Page, domain_target: str, persona: PersonaConfig, behavior: dict
) -> bool:
    """
    Tìm target trên SERP hiện tại.
    Nếu tìm thấy: pogo-stick đối thủ trước → đọc snippet → click target.
    Trả về True nếu đã vào đúng site.
    """
    target_link, real_href = await _find_target_on_serp(page, domain_target)
    if not target_link:
        return False

    print(f"   [+] BINGO! Tìm thấy '{domain_target}'.")

    # Pogo-stick đối thủ trước khi click site mình
    competitor_count = behavior.get("competitor_clicks", 0)
    if competitor_count > 0:
        await _click_competitors_with_pogo(page, domain_target, persona, competitor_count)
        # Tìm lại target sau khi pogo (DOM đã refresh sau go_back)
        target_link, real_href = await _find_target_on_serp(page, domain_target)
        if not target_link:
            print("   [-] Không tìm lại được target sau pogo-stick.")
            return False

    print(f"   [+] Đọc snippet rồi click: {(real_href or '')[:60]}...")
    await target_link.scroll_into_view_if_needed()
    await _simulate_reading_snippet(page, target_link, behavior["snippet_read_s"])
    await asyncio.sleep(behavior["hesitation_s"])
    await target_link.click()
    await page.wait_for_load_state("domcontentloaded", timeout=30000)
    return await _verify_on_target(page, domain_target)


# ─── helpers: typing & timing ────────────────────────────────────────────────

async def _type_with_persona(page: Page, text: str, persona: PersonaConfig):
    """
    Gõ từng ký tự với tốc độ + typo rate từ persona.
    Mood ảnh hưởng tốc độ: hurried -15%, relaxed +15%.
    """
    typo_chance = persona.get("typo_chance", 0.05)
    base_delay = persona.get("type_delay_ms", 100)
    multiplier = {"hurried": 0.85, "relaxed": 1.15, "curious": 1.0}.get(
        persona.get("mood", "relaxed"), 1.0
    )
    effective = int(base_delay * multiplier)
    for char in text:
        if random.random() < typo_chance:
            wrong = random.choice("abcdefghijklmnopqrstuvwxyz")
            await page.keyboard.type(wrong, delay=effective)
            await asyncio.sleep(random.uniform(0.20, 0.35))
            await page.keyboard.press("Backspace")
            await asyncio.sleep(random.uniform(0.10, 0.20))
        await page.keyboard.type(char, delay=max(10, effective + random.randint(-30, 30)))


async def _handle_autocomplete(page: Page):
    """
    40% cơ hội nhìn autocomplete dropdown rồi Escape trước khi Enter.
    Mô phỏng hành vi thật: nhiều người thấy suggestions nhưng vẫn dùng từ mình gõ.
    """
    if random.random() < 0.4:
        await asyncio.sleep(random.uniform(0.4, 1.0))
        await page.keyboard.press("Escape")
        await asyncio.sleep(random.uniform(0.2, 0.5))


async def _try_related_keyword_first(
    page: Page, keyword: str, persona: PersonaConfig
) -> bool:
    """
    Gõ từ khóa biến thể → xem SERP → nhận ra không đúng → xóa.
    Caller sẽ gõ lại từ khóa thật sau khi hàm này return True.
    Trả về False nếu skip (không có biến thể hoặc lỗi).
    """
    related = await generate_related_keyword(keyword)
    if related == keyword:
        return False

    print(f"   [🔎] Thử từ khóa biến thể trước: '{related}'")
    try:
        search_box = page.locator("input[name='q'], textarea[name='q']").locator("visible=true").first
        await search_box.click()
        await asyncio.sleep(random.uniform(0.3, 0.6))
        await _type_with_persona(page, related, persona)
        await _handle_autocomplete(page)
        await page.keyboard.press("Enter")
        await page.wait_for_load_state("domcontentloaded")

        # Nhìn SERP một chút rồi nhận ra "không đúng thứ mình cần"
        look_time = random.uniform(4, 9)
        for _ in range(random.randint(1, 3)):
            await page.mouse.wheel(0, random.randint(100, 250))
            await asyncio.sleep(look_time / 3)

        print(f"   [🔎] Không ổn, sửa lại thành: '{keyword}'")
        search_box = page.locator("input[name='q'], textarea[name='q']").locator("visible=true").first
        await search_box.click()
        await search_box.fill("")
        await asyncio.sleep(random.uniform(0.3, 0.6))
        return True
    except Exception as e:
        print(f"   [-] Bỏ qua keyword variation: {e}")
        return False


def _dwell_times(persona: PersonaConfig) -> tuple[int, int]:
    """
    t1 = thời gian đọc trang đích, t2 = trang con.
    Kết hợp mood + read_speed_ms để cho kết quả tự nhiên hơn.
    """
    mood = persona.get("mood", "relaxed")
    speed_factor = persona.get("read_speed_ms", 3000) / 3000
    if mood == "hurried":
        base = (random.randint(18, 32), random.randint(12, 22))
    elif mood == "curious":
        base = (random.randint(40, 60), random.randint(30, 50))
    else:
        base = (random.randint(28, 48), random.randint(18, 38))
    return int(base[0] * speed_factor), int(base[1] * speed_factor)


async def _scroll_serp_like_human(page: Page, persona: PersonaConfig, count: int):
    """
    Lướt SERP theo phong cách persona — nhanh hơn human_scroll vì đang tìm kiếm.
    """
    mood = persona.get("mood", "relaxed")
    for _ in range(count):
        if mood == "hurried":
            await page.mouse.wheel(0, random.randint(300, 600))
            await asyncio.sleep(random.uniform(0.4, 1.0))
        elif mood == "curious":
            await page.mouse.wheel(0, random.randint(100, 250))
            await asyncio.sleep(random.uniform(1.5, 3.0))
        else:
            await page.mouse.wheel(0, random.randint(150, 350))
            await asyncio.sleep(random.uniform(0.8, 1.8))


async def _verify_on_target(page: Page, domain_target: str) -> bool:
    await asyncio.sleep(1.5)
    # Parse domain tu URL, tranh false-positive voi substring match
    from urllib.parse import urlparse
    page_domain = urlparse(page.url).netloc.lower().lstrip("www.")
    target_clean = domain_target.lower().lstrip("www.")
    on_target = page_domain == target_clean or page_domain.endswith("." + target_clean)
    if not on_target:
        print(f"   [⚠️] Điều hướng sai — URL: {page.url[:80]}, target: {target_clean}")
    return on_target


# ─── helpers: on-site ────────────────────────────────────────────────────────

# ─── main flow ───────────────────────────────────────────────────────────────

async def run_search_flow(page: Page):
    keywords = load_keywords()
    if not keywords:
        print("   [❌] Lỗi: Chưa có Từ khóa SEO (config/keywords.json rỗng)!")
        return

    keyword = random.choice(keywords)
    raw_domain = cfg.TARGET_URL.replace("https://", "").replace("http://", "").split("/")[0]
    domain_target = raw_domain.replace("www.", "")
    total_time_spent = 0

    try:
        print(f"--- [SEARCH SEO] Từ khóa: '{keyword}' ---")

        # Song song: tạo nhân cách + hành vi tìm kiếm
        print("   [🧠] Đang tạo Nhân cách & Hành vi tìm kiếm (song song)...")
        persona, behavior = await asyncio.gather(
            generate_user_persona(cfg.TARGET_URL),
            generate_search_behavior(keyword),
        )

        # Áp dụng override từ config (cho phép user tắt từng tính năng trên UI)
        if not getattr(cfg, "POGO_STICK_ENABLE", True):
            behavior["competitor_clicks"] = 0
        else:
            behavior["competitor_clicks"] = min(
                behavior["competitor_clicks"],
                getattr(cfg, "POGO_STICK_MAX", 2),
            )
        if not getattr(cfg, "KEYWORD_VARIATION_ENABLE", True):
            behavior["try_related_first"] = False

        mood_icon = {"hurried": "⚡", "curious": "🔍", "relaxed": "😌"}.get(persona.get("mood", ""), "👤")
        print(
            f"   [{mood_icon}] User {persona.get('age')} tuổi | {persona.get('mood')} | "
            f"gõ {persona.get('type_delay_ms')}ms | typo {persona.get('typo_chance', 0)*100:.0f}%"
        )
        print(
            f"   [🗺️] KQ lướt: {behavior['glance_count']} | Pogo đối thủ: {behavior['competitor_clicks']} | "
            f"Snippet: {behavior['snippet_read_s']:.1f}s | Từ khóa biến thể: {behavior['try_related_first']}"
        )

        # ── BƯỚC 0: Warm-up trước Google ───────────────────────────────────
        await _warmup_before_search(page, persona)

        # ── BƯỚC 1: Vào Google & gõ từ khóa ───────────────────────────────
        await page.goto("https://www.google.com.vn/", wait_until="domcontentloaded", timeout=60000)
        await _accept_google_consent(page)
        await asyncio.sleep(random.uniform(1.5, 3.5))

        search_box = page.locator("input[name='q'], textarea[name='q']").locator("visible=true").first
        await search_box.wait_for(state="visible", timeout=10000)
        await search_box.click()
        await asyncio.sleep(random.uniform(0.3, 0.7))

        # Thử từ khóa biến thể trước (25% theo behavior)
        typed_related = False
        if behavior.get("try_related_first", False):
            typed_related = await _try_related_keyword_first(page, keyword, persona)

        # Gõ từ khóa thật (nếu chưa gõ biến thể)
        if not typed_related:
            await _type_with_persona(page, keyword, persona)
        await _handle_autocomplete(page)  # 40% dismiss dropdown
        await page.keyboard.press("Enter")
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(random.uniform(2.5, 4.5))

        # ── BƯỚC 2: Quét tối đa 4 trang SERP ──────────────────────────────
        found = False
        for page_num in range(1, 5):
            if _is_captcha(page):
                print("   [🚫] Phát hiện CAPTCHA. Dừng session.")
                return

            print(f"   [*] Lướt Google trang {page_num}...")
            await _scroll_serp_like_human(page, persona, count=behavior["glance_count"] + 1)

            # Tìm target + pogo đối thủ + click (gộp vào 1 helper)
            if await _locate_and_click_target(page, domain_target, persona, behavior):
                found = True
                break

            if page_num < 4:
                next_btn = page.locator("a#pnnext, a:has-text('Tiếp'), a:has-text('Next')").first
                try:
                    if await next_btn.is_visible(timeout=2000):
                        print("   [-] Không thấy ở trang này → sang trang tiếp...")
                        await next_btn.scroll_into_view_if_needed()
                        await next_btn.click()
                        await page.wait_for_load_state("domcontentloaded")
                        await asyncio.sleep(random.uniform(2.5, 4.5))
                    else:
                        break
                except Exception:
                    break

        # ── BƯỚC 3: Brand Search nếu vẫn chưa tìm thấy ────────────────────
        if not found:
            brand_name = domain_target.split(".")[0]
            advanced_keyword = f"{keyword} {brand_name}"
            print(f"   [🔍] Brand Search: '{advanced_keyword}'...")
            try:
                await page.evaluate("window.scrollTo(0, 0)")
                await asyncio.sleep(random.uniform(0.5, 1.0))
                search_box = page.locator("input[name='q'], textarea[name='q']").locator("visible=true").first
                await search_box.click()
                await search_box.fill("")
                await asyncio.sleep(random.uniform(0.3, 0.6))
                await _type_with_persona(page, advanced_keyword, persona)
                await asyncio.sleep(random.uniform(0.8, 1.5))
                await page.keyboard.press("Enter")
                await page.wait_for_load_state("domcontentloaded")
                await asyncio.sleep(random.uniform(3, 5))
                await _scroll_serp_like_human(page, persona, count=3)
                brand_behavior = {**behavior, "competitor_clicks": 0}
                found = await _locate_and_click_target(page, domain_target, persona, brand_behavior)
            except Exception as e:
                print(f"   [-] Lỗi Brand Search: {e}")

        if not found:
            print("   [❌] Không tìm thấy web sau Brand Search. Dừng session.")
            return

        # ── BƯỚC 4: Tương tác phong phú trên site ──────────────────────────
        print("   [✅] Vào web thành công từ Google. Bắt đầu tương tác...")
        await asyncio.sleep(random.uniform(2, 4))
        await auto_close_popups(page)

        # Thay thế scroll đơn thuần bằng rich_on_site_interaction
        max_pages = 3 if getattr(cfg, "THIRD_PAGE_ENABLE", True) else 2
        await rich_on_site_interaction(page, keyword, max_pages=max_pages)

        print(f"--- [SESSION END] Hoàn thành. ---")

    except Exception as e:
        print(f"--- [FAILED] Lỗi Search Flow: {e} ---")
