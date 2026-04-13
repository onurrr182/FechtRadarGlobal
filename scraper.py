import time
import re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

def fetch_page_playwright(url):
    print(f"📡 Opening {url}...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Use a large viewport to ensure elements are rendered
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()
        
        # 1. Reverted to domcontentloaded to avoid networkidle timeouts
        page.goto(url, wait_until="domcontentloaded", timeout=90000)
        time.sleep(5) # Give the initial JS time to render the table

        # 2. Bot Protection Check
        page_title = page.title()
        print(f"📄 Page Title: {page_title}")
        if "moment" in page_title.lower() or "challenge" in page_title.lower():
            print("🛑 WARNING: Blocked by Cloudflare/Bot-protection! Set headless=False.")
            # If blocked, the DOM is empty, which is why it returns 0

        # 3. Dismiss cookies if they block clicking
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
            # 4. Use Intersection Observer scrolling (crucial for Ophardt)
            # Look broadly for any link containing 'event/'
            elements = page.locator("a[href*='event/']").all()
            current_count = len(elements)
            
            if current_count > 0:
                try:
                    # Physically bring the last item into the camera view
                    elements[-1].scroll_into_view_if_needed()
                except:
                    pass
            
            # Also force page to bottom
            page.keyboard.press("End")
            
            # 5. Check for the actual "Show More" button and click it
            try:
                show_more = page.locator("a:has-text('show more'), button:has-text('show more'), .btn-load-more").first
                if show_more.is_visible(timeout=1000):
                    show_more.click()
            except:
                pass
                
            time.sleep(3) # Wait for network fetch
            
            new_elements = page.locator("a[href*='event/']").all()
            new_count = len(new_elements)
            
            if new_count > last_count:
                print(f"   ... loaded {new_count} tournaments")
                last_count = new_count
                retries = 0 # Reset retries because we found new data
            else:
                retries += 1
                print(f"   ... waiting for more data (Retry {retries}/4)")
                time.sleep(2)

        soup = BeautifulSoup(page.content(), 'html.parser')
        browser.close()
        return soup

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
