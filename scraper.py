import time
import re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

def fetch_page_playwright(url):
    print(f"📡 Opening {url}...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            # Pass some extra arguments to look less like a bot
            args=["--disable-blink-features=AutomationControlled"] 
        )
        
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            # Add accept language so it doesn't look like a raw server request
            locale="en-US",
            timezone_id="Europe/Berlin"
        )
        
        page = context.new_page()
        
        try:
            # Revert to networkidle, but give it a strict timeout
            page.goto(url, wait_until="networkidle", timeout=60000)
            
            # CRITICAL: Force it to wait until the page title actually exists
            page.wait_for_function("document.title !== ''", timeout=10000)
            
        except Exception as e:
            print(f"⚠️ Initial load warning: {e}")
            
        # 📸 TAKE A PICTURE OF WHAT THE BOT SEES
        page.screenshot(path="debug_screen.png")
        print("📸 Saved screenshot to debug_screen.png. Check this file to see what went wrong!")

        page_title = page.title()
        print(f"📄 Page Title: {page_title}")
        
        if not page_title or "moment" in page_title.lower() or "cloudflare" in page_title.lower():
            print("🛑 WARNING: Blocked by bot-protection or page failed to load.")
            browser.close()
            return None

        # Try to dismiss cookies
        try:
            page.locator("button:has-text('Accept'), button:has-text('Zustimmen')").first.click(timeout=3000)
            time.sleep(1)
        except: pass

        print("🔄 Scrolling to load all events...")
        last_count = 0
        retries = 0

        while retries < 4:
            page.keyboard.press("End")
            
            # Try clicking show more
            try:
                show_more = page.locator("a:has-text('show more'), button:has-text('show more')").first
                if show_more.is_visible(timeout=1000):
                    show_more.click()
            except: pass
                
            time.sleep(3)
            
            elements = page.locator("a[href*='event/']").all()
            new_count = len(elements)
            
            if new_count > last_count:
                print(f"   ... loaded {new_count} tournaments")
                last_count = new_count
                retries = 0 
            else:
                retries += 1
                print(f"   ... waiting for more data (Retry {retries}/4)")
                time.sleep(2)

        soup = BeautifulSoup(page.content(), 'html.parser')
        browser.close()
        return soup

# Keep your clean_city_name, detect_weapon, and detect_age_group functions below here...


# --- Helpers ---
def clean_city_name(raw_city):
    if not raw_city: return None
    cleaned = re.split(r'\s{2,}|Invitation|Results|Entries', raw_city)[0].strip()
    return cleaned if len(cleaned) > 1 else None

def detect_weapon(text):
    weapons = []
    if re.search(r'epee|degen|épée', text, re.I): weapons.append("Epee")
    if re.search(r'foil|florett', text, re.I): weapons.append("Foil")
    if re.search(r'sabre|säbel', text, re.I): weapons.append("Sabre")
    return weapons if weapons else ["Mixed"]

def detect_age_group(text):
    matches = re.findall(r'U\d+', text, re.I)
    return list(set(matches)) if matches else ["Seniors"]
