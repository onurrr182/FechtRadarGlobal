import scraper
import json
import concurrent.futures
import re
import requests
from bs4 import BeautifulSoup

# Global settings
scraper.BASE_URL = "https://fencing.ophardt.online"
scraper.CALENDAR_URL = "https://fencing.ophardt.online/en/calendar?date-from=2025-01-01&date-to=2028-12-31"

def process_entry(entry):
    try:
        url = f"{scraper.BASE_URL}/en/widget/event/{entry['id']}"
        r = requests.get(url, timeout=10)
        if r.status_code != 200: return None
        
        soup = BeautifulSoup(r.text, 'html.parser')
        full_text = soup.get_text(" ", strip=True)
        
        # Look for Country/City in the header (e.g., "GER NR Bonn")
        match = re.search(r'([A-Z]{3})\s+([A-Z0-9]{1,4})\s+([A-Za-zÄÖÜäöüßé\s\-]+)', full_text)
        if not match: return None
        
        return {
            "name": entry['name'],
            "country": match.group(1),
            "city": scraper.clean_city_name(match.group(3)),
            "weapon": scraper.detect_weapon(full_text),
            "age": scraper.detect_age_group(full_text),
            "link": url
        }
    except: return None

if __name__ == "__main__":
    soup = scraper.fetch_page_playwright(scraper.CALENDAR_URL)
   # --- ADD THIS SAFETY CHECK ---
    if not soup:
        print("❌ Scraper failed to load the page. Exiting gracefully.")
        exit(1)
    # ----------------------------- 
    entries = []
    seen = set()
    
    # Find ALL links that look like events
    for a in soup.find_all('a', href=True):
        href = a['href']
        if '/event/' in href:
            id_match = re.search(r'/event/(\d+)', href)
            if id_match:
                event_id = id_match.group(1)
                if event_id not in seen:
                    seen.add(event_id)
                    entries.append({"id": event_id, "name": a.get_text(strip=True)})

    print(f"🚀 Found {len(entries)} events to process.")

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(process_entry, entries))
        final = [res for res in results if res]

    with open('tournaments.json', 'w', encoding='utf-8') as f:
        json.dump(final, f, indent=4, ensure_ascii=False)
    
    print(f"Done! Saved {len(final)} records.")
