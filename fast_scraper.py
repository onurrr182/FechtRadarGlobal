import scraper
import json
import concurrent.futures
import re
import requests
import time
from bs4 import BeautifulSoup

# Global settings
scraper.BASE_URL = "https://fencing.ophardt.online"

def get_quarterly_ranges(start_year, end_year):
    """Generates 3-month date chunks to bypass server limits."""
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
    entries = []
    seen = set()
    
    # Define the years you want to scrape
    date_ranges = get_quarterly_ranges(2025, 2028)
    
    print(f"🗓️ Broken down into {len(date_ranges)} quarters to bypass limits.\n")
    
    for start_date, end_date in date_ranges:
        chunk_url = f"{scraper.BASE_URL}/en/calendar?date-from={start_date}&date-to={end_date}"
        print(f"--- Fetching {start_date} to {end_date} ---")
        
        soup = scraper.fetch_page_playwright(chunk_url)
        
        if not soup:
            print(f"⚠️ Failed to load {start_date} to {end_date}. Skipping to next chunk...")
            continue
            
        # Find ALL links that look like events for this specific chunk
        chunk_count = 0
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/event/' in href:
                id_match = re.search(r'/event/(\d+)', href)
                if id_match:
                    event_id = id_match.group(1)
                    if event_id not in seen:
                        seen.add(event_id)
                        entries.append({"id": event_id, "name": a.get_text(strip=True)})
                        chunk_count += 1
                        
        print(f"✅ Found {chunk_count} unique events in this chunk.\n")
        
        # Sleep for 5 seconds between chunks to look like a human browsing
        time.sleep(5)

    if not entries:
        print("❌ Scraper failed to find any events across all dates. Exiting gracefully.")
        exit(1)

    print(f"🚀 Found a grand total of {len(entries)} events to process.")

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(process_entry, entries))
        final = [res for res in results if res]

    with open('tournaments.json', 'w', encoding='utf-8') as f:
        json.dump(final, f, indent=4, ensure_ascii=False)
    
    print(f"Done! Saved {len(final)} records.")
