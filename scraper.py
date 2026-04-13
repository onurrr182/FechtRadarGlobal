import time
import re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

def fetch_page_playwright(url):
    print(f"📡 Opening {url}...")
    with sync_playwright() as p:
        # Using a real browser header to avoid being blocked
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
        page = context.new_page()
        
        page.goto(url, wait_until="networkidle")

        # CRITICAL: Wait for the tournament rows to appear
        try:
            page.wait_for_selector("a[href*='/event/']", timeout=15000)
        except:
            print("⚠️ Timeout: No event links appeared. Trying to click anyway...")

        last_count = 0
        for _ in range(15):  # Max 15 clicks to avoid infinite loops
            # Scroll and click 'Show More'
            page.keyboard.press("End")
            
            # The selector for 'show more' is often a link inside a specific div
            show_more = page.get_by_role("link", name="show more").or_(page.get_by_text("show more"))
            
            if show_more.first.is_visible():
                show_more.first.click()
                time.sleep(3) # Wait for network
            else:
                break
                
            current_count = len(page.locator("a[href*='/event/']").all())
            print(f"   ... loaded {current_count} tournaments")
            if current_count == last_count: break
            last_count = current_count

        soup = BeautifulSoup(page.content(), 'html.parser')
        browser.close()
        return soup

# Add these helpers directly here so they are available to your main script
def clean_city_name(raw_city):
    if not raw_city: return None
    # Strips everything after a double space or common keywords
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
