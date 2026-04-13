import scraper
import json
import concurrent.futures
import threading
import re
import requests
from bs4 import BeautifulSoup

def process_entry(entry):
    try:
        session = requests.Session()
        event_url = f"{scraper.BASE_URL}/en/widget/event/{entry['id']}"
        resp = session.get(event_url, timeout=10)
        if resp.status_code != 200: return None
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        page_text = soup.get_text(" ", strip=True)
        
        # Global regex for Country + City
        city_match = re.search(r'\b([A-Z]{3})\s+(?:[A-Z0-9]{1,4}\s+)?([A-ZÄÖÜa-zßäöüé][\w\-\s/\.]+)', page_text)
        if not city_match: return None
        
        country_code = city_match.group(1)
        city = scraper.clean_city_name(city_match.group(2))
        
        return {
            "name": entry['name'],
            "city": city,
            "country": country_code,
            "weapon": entry['weapon'] or scraper.detect_weapon(page_text),
            "ageGroup": scraper.detect_age_group(entry['name'] + " " + page_text),
            "pdfLink": event_url
        }
    except:
        return None

if __name__ == "__main__":
    print("📡 Starting Global Scraper...")
    soup = scraper.fetch_page_playwright(scraper.CALENDAR_URL)
    
    seen = set()
    event_entries = []
    for a in soup.find_all('a', href=True):
        m = re.search(r'/event/(\d+)', a['href'])
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            event_entries.append({"id": m.group(1), "name": a.get_text(strip=True), "weapon": []})

    print(f"🚀 Found {len(event_entries)} tournaments. Processing...")
    
    final_data = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(process_entry, event_entries))
        final_data = [r for r in results if r]

    with open('tournaments.json', 'w', encoding='utf-8') as f:
        json.dump(final_data, f, indent=4, ensure_ascii=False)
        
    print(f"Done. Saved {len(final_data)} events.")
