import scraper
import json
import concurrent.futures
import threading
import re
import requests
from bs4 import BeautifulSoup

scraper.CALENDAR_URL = "https://fencing.ophardt.online/en/calendar"

print("📡 Loading Ophardt calendar (with infinite scrolling)...")
soup = scraper.fetch_page_playwright(scraper.CALENDAR_URL)

if not soup:
    print("❌ Failed to load soup from Playwright.")
    exit()

all_links = soup.find_all('a', href=True)
event_entries = []
seen_ids = set()

for a in all_links:
    href = a.get('href', '')
    if '/widget/event/' not in href: continue
    id_match = re.search(r'/event/(\d+)', href)
    if not id_match: continue
    event_id = id_match.group(1)
    if event_id in seen_ids: continue
    
    name = a.get_text(strip=True)
    if not name or len(name) < 3 or "show more" in name.lower(): continue
    name = " ".join(name.split())
    seen_ids.add(event_id)
    
    raw_age = ""
    exact_weapon = []
    try:
        parent_td = a.find_parent('td')
        if parent_td:
            age_td = parent_td.find_next_sibling('td')
            if age_td: 
                raw_age = age_td.get_text(" ", strip=True)
                epee_td = age_td.find_next_sibling('td')
                foil_td = epee_td.find_next_sibling('td') if epee_td else None
                sabre_td = foil_td.find_next_sibling('td') if foil_td else None
                
                ws = []
                if epee_td and epee_td.find('i'): ws.append("Epee")
                if foil_td and foil_td.find('i'): ws.append("Foil")
                if sabre_td and sabre_td.find('i'): ws.append("Sabre")
                if ws: exact_weapon = ws
    except: pass
    
    event_entries.append({"id": event_id, "name": name, "raw_age": raw_age, "exact_weapon": exact_weapon})

print(f"   Found {len(event_entries)} unique event links on calendar")

geocode_lock = threading.Lock()
# Ensure geocode_city exists in your scraper.py
original_geocode = getattr(scraper, 'geocode_city', lambda c, n: (None, None))

def thread_safe_geocode(city_name, country=None):
    with geocode_lock:
        return original_geocode(city_name, country)

final_json = []
processed_count = 0
count_lock = threading.Lock()

def process_entry(entry):
    global processed_count
    try:
        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0"})

        event_url = f"{scraper.BASE_URL}/en/widget/event/{entry['id']}"
        resp = session.get(event_url, timeout=10)
        if resp.status_code != 200: return None
        
        entry_soup = BeautifulSoup(resp.text, 'html.parser')
        page_text = entry_soup.get_text(" ", strip=True)

        # Date Extraction
        date_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2}),\s*(\d{4})', page_text)
        date_str, year = "", ""
        if date_match:
            date_str = f"{date_match.group(1)} {date_match.group(2)}"
            year = date_match.group(3)
        
        # Header / City Extraction
        header_cutoff = page_text.find("Invitation")
        if header_cutoff == -1: header_cutoff = page_text.find("Results")
        header_text = page_text[:header_cutoff] if header_cutoff != -1 else page_text[:500]
        
        IOC_MAP = {
            "GER": "Germany", "USA": "United States", "FRA": "France", "GBR": "United Kingdom",
            "ITA": "Italy", "ESP": "Spain", "AUT": "Austria", "SUI": "Switzerland", "NED": "Netherlands",
            "BEL": "Belgium", "CAN": "Canada", "POL": "Poland", "HUN": "Hungary", "SWE": "Sweden"
        }
        
        city = None
        country_code = ""
        # Improved Global Regex
        city_match = re.search(r'\b([A-Z]{3})\s+(?:[A-Z0-9]{1,4}\s+)?([A-ZÄÖÜa-zßäöüé][\w\-\s/\.]+)', header_text)
        
        if city_match: 
            country_code = city_match.group(1)
            city = scraper.clean_city_name(city_match.group(2))
            actual_country = IOC_MAP.get(country_code, country_code)
            geocode_query = f"{city}, {actual_country}"
        else:
            return None

        # Geocoding
        lat, lng = thread_safe_geocode(geocode_query)
        if lat is None: lat, lng = (48.0, 14.0) 
            
        res = {
            "name": entry['name'],
            "city": city,
            "lat": round(lat, 5),
            "lng": round(lng, 5),
            "date": date_str,
            "year": year,
            "weapon": entry.get('exact_weapon') or scraper.detect_weapon(header_text),
            "ageGroup": scraper.detect_age_group(entry['name'] + " " + entry.get('raw_age', '')),
            "pdfLink": event_url
        }
        return res
    except Exception as e:
        return None
    finally:
        with count_lock:
            processed_count += 1
            if processed_count % 50 == 0:
                print(f"[{processed_count}/{len(event_entries)}] processed")

print(f"Starting threads (max 30 workers)...")
with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
    futures = [executor.submit(process_entry, entry) for entry in event_entries]
    for future in concurrent.futures.as_completed(futures):
        res = future.result()
        if res: final_json.append(res)

# Sort and Save
final_json = [f for f in final_json if f.get('date')]
final_json.sort(key=lambda x: (x.get('year', ''), x.get('date', '')))

with open('tournaments.json', 'w', encoding='utf-8') as f:
    json.dump(final_json, f, indent=4, ensure_ascii=False)

print(f"Done! Saved {len(final_json)} events.")
