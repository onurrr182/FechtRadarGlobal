import requests
from bs4 import BeautifulSoup
import re
import time
from playwright.sync_api import sync_playwright

BASE_URL = "https://fencing.ophardt.online"
CALENDAR_URL = f"{BASE_URL}/en/calendar?date-from=2025-01-01&date-to=2028-12-31"
COUNTRY_CODE = None 

def clean_city_name(raw_city):
    if not raw_city: return None
    # Remove noise words and dates often found in the header text
    city = re.split(r'\s{2,}|Invitation|Results|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec', raw_city)[0].strip()
    city = re.sub(r'[\d\s,\.\-]+$', '', city).strip()
    return city if len(city) > 1 else None

def detect_weapon(text):
    text_lower = text.lower()
    weapons = []
    if any(w in text_lower for w in ["degen", "epee", "épée"]): weapons.append("Epee")
    if any(w in text_lower for w in ["florett", "foil"]): weapons.append("Foil")
    if any(w in text_lower for w in ["säbel", "sabel", "sabre", "saber"]): weapons.append("Sabre")
    return weapons if weapons else ["Mixed"]

def detect_age_group(text):
    u_matches = re.findall(r'\bU\s?(\d+)\b', text, re.IGNORECASE)
    groups = [f"U{m}" for m in u_matches if int(m) in [9, 11, 13, 15, 17, 20, 23]]
    if any(w in text.lower() for w in ["senior", "aktive"]): groups.append("Seniors")
    if any(w in text.lower() for w in ["veteran", "vets"]): groups.append("Veterans")
    return list(set(groups)) if groups else ["Seniors"]

def fetch_page_playwright(url):
    """Infinite scroll handler to get past the 332-tournament limit."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 800})
        page.goto(url, wait_until="networkidle")
        
        last_count = 0
        while True:
            page.keyboard.press("End")
            time.sleep(2)
            # Find and click the 'show more' button
            btn = page.locator("a:has-text('show more'), button:has-text('show more')").first
            if btn.is_visible():
                btn.click()
                time.sleep(2)
            
            count = len(page.locator("a[href*='/widget/event/']").all())
            if count == last_count: break
            last_count = count
            
        content = page.content()
        browser.close()
        return BeautifulSoup(content, 'html.parser')

def geocode_city(city_name, country=None):
    # Basic fallback geocoder (replace with your Nominatim logic if needed)
    return 51.1657, 10.4515 # Default Germany
