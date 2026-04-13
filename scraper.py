import requests
from bs4 import BeautifulSoup
import json
import re
import time
import urllib.parse
import urllib.request
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---
CALENDAR_URL = "https://fencing.ophardt.online/en/calendar?date-from=2025-01-01&date-to=2028-12-31"
BASE_URL = "https://fencing.ophardt.online"
INCLUDE_MONTHS = None  # All months
COUNTRY_CODE = None    # Set to None for ALL countries (e.g., "FRA", "USA")

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
})

CITY_STOP_WORDS = ["Invitation", "Entries", "Results", "Competitions", "Other dates", "View", "Live"]

# --- UTILITIES ---

def clean_city_name(raw_city):
    if not raw_city: return None
    city = raw_city.strip()
    for stop in CITY_STOP_WORDS:
        idx = city.find(stop)
        if idx > 0: city = city[:idx].strip()
    city = re.split(r'\s{2,}|\s+\d{4}\b', city)[0].strip()
    city = re.sub(r'[\d\s,\.\-]+$', '', city).strip()
    return city if len(city) > 1 else None

def detect_weapon(text):
    text_lower = text.lower()
    weapons = []
    if any(w in text_lower for w in ["degen", "epee", "épée"]): weapons.append("Epee")
    if any(w in text_lower for w in ["florett", "foil"]): weapons.append("Foil")
    if any(w in text_lower for w in ["säbel", "sabel", "sabre", "saber"]): weapons.append("Sabre")
    return weapons if weapons else ["Mixed"]

def fetch_page_playwright(url):
    """Deep crawler: Scrolls and clicks 'Show More' until everything is loaded."""
    print(f"  --> Launching deep crawler for {url}")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=90000)

            # 1. Dismiss Cookies if they block clicking
            try:
                page.locator("button:has-text('Accept'), button:has-text('Zustimmen')").first.click(timeout=3000)
            except: pass

            # 2. Infinite Scroll + "Show More" loop
            last_count = 0
            while True:
                # Scroll to bottom to trigger lazy load
                page.keyboard.press("End")
                time.sleep(2)
                
                # Check for "Show More" button
                show_more = page.locator("button:has-text('show more'), a:has-text('show more')").first
                if show_more.is_visible():
                    show_more.click()
                    time.sleep(2)

                current_count = len(page.locator("a[href*='/widget/event/']").all())
                print(f"      ... loaded {current_count} events")
                
                if current_count == last_count: # No more new items
                    break
                last_count = current_count

            html = page.content()
            browser.close()
            return BeautifulSoup(html, 'html.parser')
    except Exception as e:
        print(f"Playwright error: {e}")
        return None

def scrape_ophardt():
    print("🚀 FechtRadar Scraper v3.0 — Global Edition")
    soup = fetch_page_playwright(CALENDAR_URL)
    if not soup: return

    all_links = soup.find_all('a', href=True)
    event_entries = []
    seen_ids = set()

    for a in all_links:
        href = a['href']
        id_match = re.search(r'/event/(\d+)', href)
        if id_match:
            event_id = id_match.group(1)
            if event_id not in seen_ids:
                seen_ids.add(event_id)
                event_entries.append({"id": event_id, "name": a.get_text(strip=True)})

    print(f"\n🔍 Processing {len(event_entries)} events globally...\n")
    final_json = []

    for idx, entry in enumerate(event_entries, 1):
        if idx % 10 == 0: print(f"Processing {idx}/{len(event_entries)}...")
        
        event_url = f"{BASE_URL}/en/widget/event/{entry['id']}"
        resp = SESSION.get(event_url)
        if resp.status_code != 200: continue
        
        event_soup = BeautifulSoup(resp.text, 'html.parser')
        header_text = event_soup.get_text(" ", strip=True)

        # --- GLOBAL REGEX ---
        # Matches: [3-letter country] [2-char region] [City Name]
        # Example: "FRA 75 Paris" or "USA CA San Jose"
        city_match = re.search(r'([A-Z]{3})\s+[A-Z0-9]{2}\s+([A-ZÄÖÜa-zßäöüéèàùìòáóúñç][\w\-\s/\.]+)', header_text)
        
        if city_match:
            country_code = city_match.group(1)
            city = clean_city_name(city_match.group(2))
        else:
            continue

        # Optional: Skip if user defined a specific country filter
        if COUNTRY_CODE and country_code != COUNTRY_CODE:
            continue

        final_json.append({
            "name": entry['name'],
            "city": city,
            "country": country_code,
            "weapon": detect_weapon(header_text),
            "link": event_url
        })

    with open('tournaments_global.json', 'w', encoding='utf-8') as f:
        json.dump(final_json, f, indent=4, ensure_ascii=False)
    
    print(f"✨ Success! Saved {len(final_json)} events.")

if __name__ == "__main__":
    scrape_ophardt()
