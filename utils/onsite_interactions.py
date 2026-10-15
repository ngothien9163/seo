"""
utils/onsite_interactions.py
Hanh vi phong phu tren site dich: CTA, tabs, gallery, form, search, depth.
"""
import asyncio
import random
from playwright.async_api import Page
from utils.mouse_helper import human_move
from utils.interactions import random_sleep, human_scroll, click_semantic_internal_link
from utils import dbg


# ─── HELPER: dong popup ─────────────────────────────────────────────────────
async def auto_close_popups(page: Page):
    try:
        close_selectors = [
            ".close-popup", ".popup-close", "#close-btn", ".close",
            "[aria-label='Close']", ".fancybox-close",
            "button[class*='close']",
        ]
        for selector in close_selectors:
            elements = await page.locator(selector).all()
            for el in elements:
                if await el.is_visible():
                    await el.click(force=True)
                    await asyncio.sleep(1)
    except Exception as e:
        dbg.warn("auto_close_popups", e)


# ─── 1. CLICK CTA BUTTONS ──────────────────────────────────────────────────
async def click_cta_buttons(page: Page) -> bool:
    cta_selectors = [
        # Text-based (Vietnamese first)
        "a:has-text('Xem thêm')",
        "a:has-text('Xem chi tiet')",
        "a:has-text('Dat hang')",
        "a:has-text('Dat mua')",
        "a:has-text('Mua ngay')",
        "a:has-text('Mua hang')",
        "a:has-text('Xem ngay')",
        "a:has-text('Dang ky')",
        "a:has-text('Nhan tu van')",
        "a:has-text('Lien he')",
        "a:has-text('Bang gia')",
        "a:has-text('Kham pha')",
        "a:has-text('Tim hieu')",
        "a:has-text('Doc them')",
        # Buttons
        "button:has-text('Xem thêm')",
        "button:has-text('Dat hang')",
        "button:has-text('Mua ngay')",
        "button:has-text('Add to Cart')",
        "button:has-text('Add to cart')",
        # English
        "a:has-text('Read more')",
        "a:has-text('Read More')",
        "a:has-text('Details')",
        "a:has-text('Shop now')",
        "a:has-text('Learn more')",
        "a:has-text('Contact')",
        "a:has-text('Book now')",
        # Generic class-based
        "button[class*='btn']",
        "a[class*='btn']",
        "a[class*='cta']",
        "button[class*='cta']",
        "a[class*='action']",
        "a[class*='button']",
        "button[class*='button']",
        "[class*='view-more'] a, [class*='viewmore'] a",
        "[class*='read-more'] a, [class*='readmore'] a",
    ]
    random.shuffle(cta_selectors)

    for selector in cta_selectors:
        try:
            buttons = await page.locator(selector).all()
            for btn in buttons:
                if await btn.is_visible():
                    txt = await btn.inner_text()
                    await btn.scroll_into_view_if_needed()
                    await random_sleep(0.3, 0.8)
                    box = await btn.bounding_box()
                    if box:
                        cx = box['x'] + box['width']/2 + random.randint(-3, 3)
                        cy = box['y'] + box['height']/2 + random.randint(-3, 3)
                        await human_move(page, cx, cy)
                        await asyncio.sleep(random.uniform(0.2, 0.5))
                        await btn.click(force=True)
                        print(f"   [CTA] Click: '{txt.strip()[:30]}'")
                        return True
        except Exception as e:
            dbg.warn("click_cta_buttons", e)
            continue
    return False


# ─── 2. SWITCH TABS ────────────────────────────────────────────────────────
async def switch_tabs(page: Page) -> bool:
    tab_selectors = [
        "a[role='tab']",
        "button[role='tab']",
        ".tab a", ".tab-link",
        ".nav-tabs a",
        "[data-tab]",
        "[class*='tab'] a",
        "a:has-text('Mo ta')",
        "a:has-text('Danh gia')",
        "a:has-text('Chi tiet')",
        "a:has-text('Binh luan')",
        "a:has-text('Description')",
        "a:has-text('Reviews')",
        "a:has-text('Specifications')",
        # Them selector cho tab thuong gap
        "li[class*='tab'] a",
        "[class*='tab-panel']"
    ]
    random.shuffle(tab_selectors)

    for selector in tab_selectors:
        try:
            tabs = await page.locator(selector).all()
            for tab in tabs:
                txt = await tab.inner_text()
                if not txt or len(txt.strip()) < 2:
                    continue
                if await tab.is_visible():
                    await tab.scroll_into_view_if_needed()
                    await random_sleep(0.3, 0.7)
                    await tab.click(force=True)
                    print(f"   [TAB] Chuyen tab: '{txt.strip()[:25]}'")
                    await asyncio.sleep(random.uniform(1.5, 3.0))
                    await human_scroll(page, duration=random.randint(5, 12))
                    return True
        except Exception as e:
            dbg.warn("switch_tabs", e)
            continue
    return False


# ─── 3. CLICK RANDOM VISIBLE IMAGE ─────────────────────────────────────────
async def click_visible_image(page: Page) -> bool:
    """
    Click 1-2 anh bat ky tren trang (product img, banner, logo).
    Rat thuong gap tren beauty/ecommerce site.
    """
    img_selectors = [
        "img[class*='product']",
        "img[class*='banner']",
        "img[class*='thumb']",
        "img[class*='gallery']",
        "img[class*='slider']",
        "img[class*='card']",
        "img[class*='img']",
        ".slick-slide img",
        ".owl-item img",
        "[class*='gallery'] img",
        "[class*='slider'] img",
        "[class*='carousel'] img",
        ".product-thumb img",
        ".thumbnail img",
        "a[class*='lightbox']",
        "[data-lightbox]",
        # Neu khong co selector nao match, lay img co alt
        "img[alt]:not([alt=''])",
        "article img",
        "main img",
    ]
    random.shuffle(img_selectors)

    for selector in img_selectors:
        try:
            imgs = await page.locator(selector).all()
            visible_imgs = [i for i in imgs if await i.is_visible()]
            if not visible_imgs:
                continue
            # Chon 1-2 anh
            sample = random.sample(visible_imgs, min(random.randint(1, 2), len(visible_imgs)))
            for img in sample:
                await img.scroll_into_view_if_needed()
                await random_sleep(0.3, 0.8)
                await img.click(force=True)
                alt = await img.get_attribute("alt") or "no-alt"
                print(f"   [IMG] Click anh: '{alt[:25]}'")
                await asyncio.sleep(random.uniform(1.0, 2.0))
            return True
        except Exception as e:
            dbg.warn("click_visible_image", e)
            continue
    return False


# ─── 4. SITE SEARCH ────────────────────────────────────────────────────────
async def search_on_site(page: Page, keyword: str) -> bool:
    search_selectors = [
        "input[type='search']",
        "input[name='s']",
        "input[name='search']",
        "input[name='q']",           # nhieu site dung q
        "input[placeholder*='search' i]",
        "input[placeholder*='tim' i]",
        "input[placeholder*='Search' i]",
        "form[role='search'] input",
        "#searchbox input",
        ".search-form input",
        "[class*='search'] input",
    ]

    search_terms = [
        keyword,
        keyword.split()[0] if len(keyword.split()) > 1 else keyword,
    ]
    search_term = random.choice(search_terms)

    for selector in search_selectors:
        try:
            inputs = await page.locator(selector).all()
            for inp in inputs:
                if await inp.is_visible():
                    await inp.scroll_into_view_if_needed()
                    await random_sleep(0.3, 0.7)
                    await inp.click()
                    await asyncio.sleep(random.uniform(0.3, 0.6))
                    for ch in search_term:
                        await inp.type(ch, delay=random.randint(40, 120))
                    await asyncio.sleep(random.uniform(0.5, 1.5))
                    await page.keyboard.press("Enter")
                    print(f"   [SEARCH] Noi bo: '{search_term}'")
                    try:
                        await page.wait_for_load_state("domcontentloaded", timeout=10000)
                    except Exception as e:
                        dbg.warn("search_on_site wait_load", e)
                    await asyncio.sleep(random.uniform(2, 4))
                    await human_scroll(page, duration=random.randint(8, 15))
                    return True
        except Exception as e:
            dbg.warn("search_on_site", e)
            continue
    return False


# ─── 5. SUBSCRIPTION FORM ──────────────────────────────────────────────────
async def fill_subscription_form(page: Page) -> bool:
    email_selectors = [
        "input[type='email']",
        "input[name='email']",
        "input[placeholder*='email' i]",
        "input[placeholder*='mail' i]",
        "input[aria-label*='email' i]",
        "#email",
        ".email-input",
        "[class*='email'] input",
    ]

    fake_emails = [
        f"ngdung{random.randint(1000,9999)}@gmail.com",
        f"khachhang{random.randint(1000,9999)}@yahoo.com",
        f"tvien{random.randint(1000,9999)}@outlook.com",
    ]

    submit_selectors = [
        "button[type='submit']",
        "button:has-text('Dang ky')",
        "button:has-text('Subscribe')",
        "button:has-text('Gui')",
        "button:has-text('Send')",
        "button:has-text('Nhan tin')",
        "input[type='submit']",
        "button:has-text('Dang ky nhan tin')",
    ]

    email = random.choice(fake_emails)

    for selector in email_selectors:
        try:
            inputs = await page.locator(selector).all()
            for inp in inputs:
                if await inp.is_visible():
                    await inp.scroll_into_view_if_needed()
                    await random_sleep(0.5, 1.5)
                    await inp.click()
                    await asyncio.sleep(random.uniform(0.3, 0.6))
                    for ch in email:
                        await inp.type(ch, delay=random.randint(40, 100))
                    await asyncio.sleep(random.uniform(0.5, 1.5))

                    for sub_sel in submit_selectors:
                        try:
                            subs = await page.locator(sub_sel).all()
                            for sub in subs:
                                if await sub.is_visible():
                                    await sub.scroll_into_view_if_needed()
                                    box = await sub.bounding_box()
                                    if not box:
                                        continue
                                    sx = box['x'] + box['width']/2 + random.randint(-3, 3)
                                    sy = box['y'] + box['height']/2 + random.randint(-3, 3)
                                    await human_move(page, sx, sy)
                                    await asyncio.sleep(random.uniform(0.2, 0.5))
                                    await sub.click(force=True)
                                    print(f"   [EMAIL] Dien form: {email}")
                                    await asyncio.sleep(random.uniform(2, 4))
                                    return True
                        except Exception as e:
                            dbg.warn("fill_subscription_form submit", e)
                            continue
        except Exception as e:
            dbg.warn("fill_subscription_form", e)
            continue
    return False


# ─── 6. SCROLL TO SPECIFIC SECTION ────────────────────────────────────────
async def scroll_to_content_section(page: Page) -> bool:
    section_selectors = [
        "section", "article",
        "[class*='related']",
        "[class*='product']",
        "[class*='comment']",
        "[class*='review']",
        "[class*='service']",
        "[class*='featured']",
        "[class*='popular']",
        "[class*='news']",
        "[class*='blog']",
        "[class*='footer']",
        "[id*='related']",
        "[id*='product']",
        "footer",
    ]
    random.shuffle(section_selectors)

    for selector in section_selectors:
        try:
            sections = await page.locator(selector).all()
            for section in sections:
                if await section.is_visible():
                    await section.scroll_into_view_if_needed()
                    tag = await section.get_attribute("class") or selector
                    print(f"   [SECTION] Scroll den: '{str(tag)[:30]}'")
                    await random_sleep(0.5, 1.5)
                    await human_scroll(page, duration=random.randint(5, 12))
                    return True
        except Exception as e:
            dbg.warn("scroll_to_content_section", e)
            continue
    return False


# ─── 7. CLICK NAVIGATION MENU ──────────────────────────────────────────────
async def click_nav_menu(page: Page) -> bool:
    """Click random item trong navigation menu."""
    nav_selectors = [
        "nav a",
        "header a",
        "[class*='menu'] a",
        "[class*='nav'] a",
        "[class*='header'] a",
        "[class*='navbar'] a",
        ".main-menu a",
        "#menu a",
        "ul[class*='nav'] li a",
    ]
    random.shuffle(nav_selectors)

    # Cac link can tranh (trang chu, login, cart, account)
    skip_keywords = ["trang chu", "home", "dang nhap", "login",
                     "dang ky", "register", "gio hang", "cart",
                     "account", "tai khoan"]

    for selector in nav_selectors:
        try:
            links = await page.locator(selector).all()
            visible_links = [l for l in links if await l.is_visible()]
            if not visible_links:
                continue
            # Loc bo link can tranh
            good_links = []
            for l in visible_links:
                txt = (await l.inner_text()).strip().lower()
                href = (await l.get_attribute("href") or "").lower()
                jump = any(s in txt or s in href for s in skip_keywords)
                if len(txt) > 1 and not jump:
                    good_links.append(l)
            if not good_links:
                continue
            target = random.choice(good_links)
            txt = await target.inner_text()
            await target.scroll_into_view_if_needed()
            await random_sleep(0.3, 0.7)
            await target.click(force=True)
            print(f"   [NAV] Click menu: '{txt.strip()[:25]}'")
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception as e:
                dbg.warn("click_nav_menu wait_load", e)
            await asyncio.sleep(random.uniform(2, 4))
            await human_scroll(page, duration=random.randint(10, 20))
            return True
        except Exception as e:
            dbg.warn("click_nav_menu", e)
            continue
    return False


# ─── 8. BACK & FORTH ───────────────────────────────────────────────────────
async def back_and_forth(page: Page) -> bool:
    try:
        can_go_back = await page.evaluate("window.history.length > 1")
        if not can_go_back:
            return False

        await asyncio.sleep(random.uniform(0.5, 1.0))
        print("   [BACK] Back button...")
        await page.go_back(wait_until="domcontentloaded")
        await asyncio.sleep(random.uniform(1.5, 3.0))
        await human_scroll(page, duration=random.randint(5, 10))

        if random.random() < 0.5:
            await asyncio.sleep(random.uniform(0.5, 1.0))
            print("   [FORWARD] Forward button...")
            await page.go_forward(wait_until="domcontentloaded")
            await asyncio.sleep(random.uniform(1.5, 3.0))
            await human_scroll(page, duration=random.randint(5, 10))

        return True
    except Exception as e:
        return False


# ─── 9. MASTER: RICH ON-SITE INTERACTION ──────────────────────────────────
async def rich_on_site_interaction(page: Page, keyword: str, max_pages: int = 3):
    """
    Hanh vi phong phu tren site dich.
    """
    pages_read = 1
    actions_done = []

    # Trang 1 (landing page)
    print(f"   [SITE] Tuong tac phong phu — trang {pages_read}...")

    # Tat ca hanh dong (xao tron thu tu)
    actions = [
        ("cta", click_cta_buttons),
        ("tabs", switch_tabs),
        ("img", click_visible_image),
        ("nav", click_nav_menu),
        ("section", scroll_to_content_section),
        ("search", lambda p: search_on_site(p, keyword)),
        ("email", fill_subscription_form),
    ]
    random.shuffle(actions)

    # ~70% moi hanh dong xay ra
    for name, func in actions:
        if random.random() < 0.70:
            try:
                if await func(page):
                    actions_done.append(name)
                    await asyncio.sleep(random.uniform(1, 3))
            except Exception as e:
                pass

    # Click internal link => trang 2,3...
    while pages_read < max_pages:
        try:
            clicked = await click_semantic_internal_link(page, keyword)
        except Exception as e:
            dbg.warn("rich_on_site semantic_click", e)
            clicked = False
        if clicked:
            pages_read += 1
            print(f"   [SITE] Tuong tac — trang {pages_read}...")
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception as e:
                dbg.warn("rich_on_site wait_load", e)
            await auto_close_popups(page)
            await asyncio.sleep(random.uniform(1, 3))

            await human_scroll(page, duration=random.randint(15, 25))

            # Sub-actions tren trang sau (1-2 hanh dong)
            sub = random.sample(actions, random.randint(1, 2))
            for name, func in sub:
                if random.random() < 0.60:
                    try:
                        if await func(page):
                            actions_done.append(f"{name}(p{pages_read})")
                            await asyncio.sleep(random.uniform(1, 2))
                    except Exception as e:
                        dbg.warn("rich_on_site sub_action", e)
        else:
            break

    # Back & Forth
    if random.random() < 0.35 and pages_read >= 2:
        try:
            await back_and_forth(page)
            actions_done.append("back/forth")
        except Exception as e:
            dbg.warn("rich_on_site back_forth", e)

    # Summary
    acts = ", ".join(actions_done) if actions_done else "(khong co)"
    print(f"   [SITE] => {pages_read} trang | Hanh dong: {acts}")
