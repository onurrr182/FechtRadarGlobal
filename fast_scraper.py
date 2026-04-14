import scraper
import json
import concurrent.futures
import threading
import urllib.request
import urllib.parse
import re
import requests
import time
from bs4 import BeautifulSoup

# Global settings
scraper.BASE_URL = "https://fencing.ophardt.online"

# --- THREAD-SAFE GEOCODER & CLEANER ---
GEO_CACHE = {}
geo_lock = threading.Lock()

def clean_city_name(raw_city):
    """Strips out fencing terminology so the map doesn't get confused."""
    if not raw_city: return None
    
    # Split by double spaces or newlines first
    cleaned = re.split(r'\s{2,}|\n', raw_city)[0].strip()
    
    # Aggressive list of Fencing/Ophardt noise words
    noise_words = [
        'Men', 'Women', 'Foil', 'Epee', 'Sabre', 'épée', 'säbel', 'florett', 'degen',
        'World', 'Cup', 'Championship', 'Grand Prix', 'Satellite', 'Veteran', 'U17', 'U20', 'U14',
        'Cadet', 'Junior', 'Senior', 'Team', 'Individual', 'Invitation', 'Results', 'Entries', 'FIE'
    ]
    
    # Chop off the string the moment it hits a noise word
    for word in noise_words:
        pattern = re.compile(rf'\b{word}\b', re.IGNORECASE)
        match = pattern.search(cleaned)
        if match:
            cleaned = cleaned[:match.start()].strip()
            
    # Remove trailing punctuation and numbers
    cleaned = re.sub(r'[\d\s,\.\-\/]+$', '', cleaned).strip()
    return cleaned if len(cleaned) > 1 else None

def get_coordinates(city, iso_code):
    """Uses strict ISO limits so pins don't jump continents."""
    if not iso_code: iso_code = ""
        
    query = f"{city}_{iso_code}"
    with geo_lock:
        if query in GEO_CACHE: return GEO_CACHE[query]
            
        time.sleep(1.1) # Respect OSM 1 request/sec limit
        
        # Attempt 1: Search by City strictly within the Country Code
        try:
            url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(city)}&countrycodes={iso_code}&format=json&limit=1"
            req = urllib.request.Request(url, headers={"User-Agent": "FechtRadarMap/9.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                if data:
                    res = (round(float(data[0]["lat"]), 5), round(float(data[0]["lon"]), 5))
                    GEO_CACHE[query] = res
                    return res
        except Exception: pass
            
        # Attempt 2: If city fails entirely, drop a pin in the center of the country
        try:
            time.sleep(1.1)
            url = f"https://nominatim.openstreetmap.org/search?country={iso_code}&format=json&limit=1"
            req = urllib.request.Request(url, headers={"User-Agent": "FechtRadarMap/9.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                if data:
                    res = (round(float(data[0]["lat"]), 5), round(float(data[0]["lon"]), 5))
                    GEO_CACHE[query] = res
                    return res
        except Exception: pass

        # If completely lost, DO NOT dump it in Germany. Drop the event.
        GEO_CACHE[query] = (None, None)
        return (None, None)

# --- SCRAPER LOGIC ---

def get_quarterly_ranges(start_year, end_year):
    """Generates 3-month chunks to bypass server limits."""
    quarters = []
    for year in range(start_year, end_year + 1):
        quarters.extend([
            (f"{year}-01-01", f"{year}-03-31"),
            (f"{year}-04-01", f"{year}-06-30"),
            (f"{year}-07-01", f"{year}-09-30"),
            (f"{year}-10-01", f"{year}-12-31")
        ])
    return quarters

def process_entry(entry):
    try:
        url = f"{scraper.BASE_URL}/en/widget/event/{entry['id']}"
        r = requests.get(url, timeout=10)
        if r.status_code != 200: return None
        
        soup = BeautifulSoup(r.text, 'html.parser')

        # --- THE UI NUKER ---
        # Destroy navigation, footers, and language menus before reading text
        for ui in soup.find_all(['nav', 'header', 'footer', 'ul']):
            ui.decompose()
        for ui in soup.find_all(class_=re.compile(r'nav|lang|menu|breadcrumb|topbar|btn', re.I)):
            ui.decompose()
            
        # Only look at the top 400 characters to ignore the Ophardt footer
        header_text = soup.get_text(" ", strip=True)[:400] 
        
        # FIE Code to ISO Code Mapping
        FIE_TO_ISO = {
            "GER": "de", "FRA": "fr", "ITA": "it", "ESP": "es", "GBR": "gb", "USA": "us", 
            "CAN": "ca", "MEX": "mx", "BRA": "br", "ARG": "ar", "CHI": "cl", "COL": "co",
            "EGY": "eg", "RSA": "za", "ALG": "dz", "MAR": "ma", "SEN": "sn",
            "UAE": "ae", "KSA": "sa", "QAT": "qa", "KWT": "kw", "IRI": "ir",
            "CHN": "cn", "JPN": "jp", "KOR": "kr", "HKG": "hk", "TPE": "tw", "SGP": "sg", 
            "PHI": "ph", "IND": "in", "KAZ": "kz", "UZB": "uz", "AUS": "au", "NZL": "nz",
            "POL": "pl", "HUN": "hu", "CZE": "cz", "SVK": "sk", "ROU": "ro", "BUL": "bg", 
            "GRE": "gr", "TUR": "tr", "CRO": "hr", "SRB": "rs", "SLO": "si", "UKR": "ua", 
            "GEO": "ge", "AUT": "at", "SUI": "ch", "BEL": "be", "NED": "nl", "LUX": "lu",
            "SWE": "se", "DEN": "dk", "NOR": "no", "FIN": "fi", "EST": "ee", "LAT": "lv", 
            "LTU": "lt", "ISL": "is", "IRL": "ie", "POR": "pt", "CUB": "cu", "PUR": "pr"
        }
        
        # Fixed Regex: Removed numbers from the city capturing group
        valid_codes = "|".join(FIE_TO_ISO.keys())
        match = re.search(rf'\b({valid_codes})\s+(?:[A-Z0-9]{{1,3}}\s+)?([A-ZÄÖÜa-zßäöüéèàùìòáóúñç][A-Za-zÄÖÜa-zßäöüéèàùìòáóúñç\-\s\./]+)', header_text)
        
        if not match: return None
        
        country_code = match.group(1)
        city = clean_city_name(match.group(2))
        iso_code = FIE_TO_ISO.get(country_code, "")
        
        lat, lng = get_coordinates(city, iso_code)
        
        # If the map absolutely cannot find it, drop the event so we don't put pins in the ocean
        if lat is None or lng is None: return None
        
        # Extract Date
        date_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2}),\s*(\d{4})', header_text)
        date_str = f"{date_match.group(1)} {date_match.group(2)}" if date_match else ""
        year = date_match.group(3) if date_match else ""
        
        return {
            "name": entry['name'],
            "country": country_code,
            "city": city,
            "lat": lat,
            "lng": lng,
            "date": date_str,
            "year": year,
            "weapon": scraper.detect_weapon(header_text),
            "ageGroup": scraper.detect_age_group(header_text),
            "pdfLink": url
        }
    except: return None


if __name__ == "__main__":
    entries = []
    seen = set()
    date_ranges = get_quarterly_ranges(2025, 2028)
    
    print(f"🗓️ Broken down into {len(date_ranges)} quarters...\n")
    
    for start_date, end_date in date_ranges:
        chunk_url = f"{scraper.BASE_URL}/en/calendar?date-from={start_date}&date-to={end_date}"
        print(f"--- Fetching {start_date} to {end_date} ---")
        
        soup = scraper.fetch_page_playwright(chunk_url)
        if not soup:
            continue
            
        chunk_count = 0
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/event/' in href:
                id_match = re.search(r'/event/(\d+)', href)
                if id_match:
                    event_id = id_match.group(1)
                    
                    name = a.get_text(separator=" ", strip=True)
                    name = re.sub(r'\s+', ' ', name) # Clean up extra spaces
                    
                    if len(name) > 3 and "show more" not in name.lower():
                        if event_id not in seen:
                            seen.add(event_id)
                            entries.append({"id": event_id, "name": name})
                            chunk_count += 1
                        
        print(f"✅ Found {chunk_count} unique events. Sleeping 5s...\n")
        time.sleep(5)

    print(f"🚀 Found {len(entries)} events to process. Mapping coordinates... (This may take a few minutes)")

    # Process events with ThreadPool
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(process_entry, entries))
        final = [res for res in results if res]
        
    # Sort chronologically by year, then date string
    final = [f for f in final if f.get('date')]
    final.sort(key=lambda x: (x.get('year', ''), x.get('date', '')))

    with open('tournaments.json', 'w', encoding='utf-8') as f:
        json.dump(final, f, indent=4, ensure_ascii=False)
    
    print(f"Done! Saved {len(final)} records with mapped locations.")
