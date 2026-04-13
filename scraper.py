import time
import re
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from bs4 import BeautifulSoup

def fetch_page_playwright(url):
    print(f"📡 Opening {url} with Stealth Mode (v2 API)...")
    
    # The new v2.0+ API wraps the entire Playwright sync manager
    with Stealth().use_sync(sync_playwright()) as p:
        # Launch Chromium headless
        browser = p.chromium.launch(headless=True)
        
        # Setup context to look like a standard desktop browser
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="en-US"
        )
        page = context.new_page()
        
        try:
            # Wait for the network to quiet down
            page.goto(url, wait_until="networkidle", timeout=60000)
            # Ensure the document title actually renders before continuing
            page.wait_for_function("document.title !== ''", timeout=15000)
        except Exception as e:
            print(f"⚠️ Initial load warning: {e}")
            
        page_title = page.title()
        print(f"📄 Page Title: {page_title}")
        
        # Cloudflare / Bot block detection
        if not page_title or "moment" in page_title.lower() or "challenge" in page_title.lower():
            print("🛑 WARNING: Still blocked by bot-protection.")
            browser.close()
            return None

        # Dismiss cookies if the banner appears
        try:
            cookie_btn = page.locator("button:has-text('Accept'), button:has-text('Zustimmen')").first
            if cookie_btn.is_visible(timeout=3000):
                cookie_btn.click()
                time.sleep(1)
        except:
            pass

        print("🔄 Scrolling to load all events...")
        last_count = 0
        retries = 0

        while retries < 4:
            # Force scroll to the bottom
            page.keyboard.press("End")
            
            # Click the 'show more' button if it exists
            try:
                show_more = page.locator("a:has-text('show more'), button:has-text('show more')").first
                if show_more.is_visible(timeout=1000):
                    show_more.click()
            except:
                pass
                
            time.sleep(3) # Wait for network fetch
            
            # Count the loaded tournaments
            elements = page.locator("a[href*='event/']").all()
            new_count = len(elements)
            
            if new_count > last_count:
                print(f"   ... loaded {new_count} tournaments")
                last_count = new_count
                retries = 0  # Found new data, reset retries
            else:
                retries += 1
                print(f"   ... waiting for more data (Retry {retries}/4)")
                time.sleep(2)

        soup = BeautifulSoup(page.content(), 'html.parser')
        browser.close()
        return soup

# --- Helper Functions ---
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
