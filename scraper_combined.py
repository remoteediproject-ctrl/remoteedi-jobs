import requests
import csv
import datetime
import time
import os
import json
from bs4 import BeautifulSoup
import re

OUTPUT_FILE = "edi_jobs_all.csv"
CACHE_FILE = "jsearch_cache.json"

# 🔥 TU WPISZ SWOJE KLUCZE (nie ENV)
ADZUNA_APP_ID  = os.environ.get("ADZUNA_APP_ID",  "03049e54")
ADZUNA_APP_KEY = os.environ.get("ADZUNA_APP_KEY", "03494e483e28beff7d8ee54573bac109")
JSEARCH_KEY    = os.environ.get("JSEARCH_KEY",    "fd093a3128msh485b2b1ce1651c6p108b94jsn4e84230e71cc")


# ── CACHE RESET ─────────────────────

if os.path.exists(CACHE_FILE):
    os.remove(CACHE_FILE)
    print("🧹 Cache cleared")


# ── Helpery ───────────────────────────────────────────────────────────────────

def is_real_edi_job(title: str) -> bool:
    t = title.lower()
    for term in ["edi ", " edi", "/edi", "edi/", "electronic data interchange", "x12", "edifact", "idoc"]:
        if term in t:
            return True
    return False

def is_relevant(title):
    t = title.lower()

    keywords = [
        "edi",
        "integration",
        "sap",
        "boomi",
        "mulesoft",
        "b2b",
        "idoc"
    ]

    return any(k in t for k in keywords)

# ── CLASSIFICATION ─────────────────────

def categorize_job(title: str, description: str) -> str:
    text = ((title or "") + " " + (description or "")).lower()
    if any(k in text for k in ["837", "835", "834", "270", "271", "hipaa", "healthcare", "medicaid", "medicare"]):
        return "Healthcare EDI"
    elif any(k in text for k in ["sap", "idoc"]):
        return "SAP EDI"
    elif any(k in text for k in ["850", "856", "logistics", "retail", "warehouse", "3pl", "supply chain"]):
        return "Logistics & Retail"
    elif any(k in text for k in ["developer", "engineer", "programmer", "mapping"]):
        return "EDI Developer"
    elif any(k in text for k in ["analyst", "specialist"]):
        return "EDI Analyst"
    elif any(k in text for k in ["coordinator"]):
        return "EDI Coordinator"
    else:
        return "EDI General"

def normalize_title(title: str) -> str:
    """Upraszcza tytul do porownania - usuwa szczegoly w nawiasach."""
    import re
    t = title.lower().strip()
    t = re.sub(r"[\(\[].*?[\)\]]", "", t)  # usuwa (Remote), (Work from Home) etc
    t = re.sub(r"\s+", " ", t).strip()
    return t

def deduplicate(jobs: list) -> list:
    """Deduplikuje po znormalizowanym tytule + firmie."""
    seen = set()
    unique = []
    for job in jobs:
        key = (normalize_title(job["title"]), job["company"].lower().strip())
        if key not in seen:
            seen.add(key)
            unique.append(job)
    return unique


def is_edi(title):
    return "edi" in title.lower()


# ════════════════════════════════════════════════════════════════════════════
# ADZUNA SCRAPER
# ════════════════════════════════════════════════════════════════════════════

# Kraje Adzuna z kodem i nazwa
ADZUNA_COUNTRIES = [
    ("us", "USA"),
    ("gb", "UK"),
    ("ca", "Canada"),
    ("au", "Australia"),
    ("de", "Germany"),
    ("nl", "Netherlands"),
]

ADZUNA_QUERIES = [
    "EDI analyst",
    "EDI developer",
    "EDI specialist",
    "EDI engineer",
    "EDI coordinator",
    "electronic data interchange",
]

def fetch_adzuna(query: str, country_code: str, country_name: str) -> list:
    url = f"https://api.adzuna.com/v1/api/jobs/{country_code}/search/1"
    params = {
        "app_id":           ADZUNA_APP_ID,
        "app_key":          ADZUNA_APP_KEY,
        "what":             query,
        "results_per_page": 50,
        "sort_by":          "date",
        "full_time":        1,
        "content-type":     "application/json",
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        return r.json().get("results", [])
    except:
        return []


COUNTRY_CURRENCY = {
    "USA":         ("$",  ""),
    "UK":          ("£",  ""),
    "Canada":      ("CA$",""),
    "Australia":   ("A$", ""),
    "Germany":     ("€",  ""),
    "Netherlands": ("€",  ""),
}


def parse_adzuna_job(job: dict, country_name: str) -> dict:
    title   = job.get("title", "").strip()
    company = job.get("company", {}).get("display_name", "")
    location_data = job.get("location", {})
    loc_display = location_data.get("display_name", "")
    description = job.get("description", "")
    url = job.get("redirect_url", "")

    if not is_real_edi_job(title):
        return None

    # Wyklucz aggregatory
    aggregators = ["jobgether", "jooble", "talent.com", "jobrapido", "neuvoo"]
    if any(a in company.lower() for a in aggregators):
        return None

    # Remote filter
    remote_terms = ["remote", "work from home", "wfh", "telework"]
    is_remote = (
        any(t in title.lower() for t in remote_terms) or
        any(t in description.lower()[:800] for t in remote_terms) or
        loc_display.strip().lower() in ["us", "gb", "ca", "au", "de", "nl", ""]
    )
    if not is_remote:
        # Dla krajow poza US bądź bardziej elastyczny — "US" to jasny signal
        if country_name != "USA":
            is_remote = True  # inne kraje — zakładamy remote jeśli Adzuna zwrócił

    if not is_remote:
        return None

    # Salary z poprawna waluta
    s_min = job.get("salary_min")
    s_max = job.get("salary_max")
    symbol = COUNTRY_CURRENCY.get(country_name, ("$", ""))[0]
    if s_min and s_max and int(s_min) != int(s_max):
        salary = f"{symbol}{int(s_min):,} - {symbol}{int(s_max):,}"
    else:
        salary = ""

    # Data
    created = job.get("created", "")
    try:
        dt = datetime.datetime.fromisoformat(created.replace("Z", "+00:00"))
        posted = dt.date().isoformat()
    except:
        posted = datetime.date.today().isoformat()

    # Lokalizacja
    if any(t in title.lower() + description.lower()[:300] for t in ["remote", "work from home"]):
        location = f"Remote {country_name}"
    elif loc_display and loc_display.upper() not in ["US", "GB", "CA", "AU", "DE", "NL"]:
        location = f"{loc_display}, {country_name}"
    else:
        location = f"Remote {country_name}"

    return {
        "title":          title,
        "company":        company,
        "location":       location,
        "salary":         salary,
        "posted":         posted,
        "url":            url,
        "specialization": categorize_job(title, description),
        "source":         "Adzuna",
        "tags":           "",
    }


def run_adzuna() -> list:
    print("\n── ADZUNA ──────────────────────────────────────")
    all_jobs = []

    for country_code, country_name in ADZUNA_COUNTRIES:
        print(f"\n  [{country_name}]")
        for query in ADZUNA_QUERIES:
            results = fetch_adzuna(query, country_code, country_name)
            for r in results:
                job = parse_adzuna_job(r, country_name)
                if job:
                    all_jobs.append(job)
            time.sleep(0.5)

    print(f"\n  Adzuna total: {len(all_jobs)} jobów (przed dedup)")
    return all_jobs


# ── JSEARCH ─────────────────────

def run_jsearch():
    print("\n── JSEARCH ──")
    jobs = []

    url = "https://jsearch.p.rapidapi.com/search"

    headers = {
        "X-RapidAPI-Key": JSEARCH_KEY,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
    }

    params = {
        "query": "EDI remote",
        "num_pages": 1
    }

    try:
        r = requests.get(url, headers=headers, params=params)
        data = r.json().get("data", [])

        for j in data:
            title = j.get("job_title", "")
            if not is_edi(title):
                continue

            jobs.append({
                "title": title,
                "company": j.get("employer_name", ""),
                "location": "Remote",
                "salary": "",
                "posted": datetime.date.today().isoformat(),
                "url": j.get("job_apply_link"),
                "source": "JSearch",
                "specialization": categorize_job(title, j.get("job_description", "")),
                "tags": ""
            })



    except Exception as e:
        print("JSearch error:", e)

    print("JSearch:", len(jobs))
    return jobs



# ── DICE SCRAPER ─────────────────────────────────────────

DICE_QUERIES = ["edi+remote"]
DICE_MAX_PAGES = 5
DICE_HEADERS = {"User-Agent": "Mozilla/5.0"}

def fetch_page(query, page):
    url = f"https://www.dice.com/jobs/q-{query}-jobs?page={page}"

    r = requests.get(url, headers=DICE_HEADERS)

    if r.status_code != 200:
        print("❌ Failed:", r.status_code)
        return None

    return r.text

def parse_posted_date(date_text):
    """
    Konwertuje tekst 'Posted 2 days ago' na datę ISO
    """
    if not date_text:
        return datetime.date.today().isoformat()
    
    date_text = date_text.lower().strip()
    today = datetime.date.today()
    
    if "today" in date_text or "just posted" in date_text:
        return today.isoformat()
    
    if "yesterday" in date_text:
        return (today - datetime.timedelta(days=1)).isoformat()
    
    # "Posted 2 days ago", "2 days ago", "3d ago"
    import re
    
    # Szukamy liczby
    match = re.search(r'(\d+)\s*(day|d|hour|h|week|w|month|mo)', date_text)
    if match:
        num = int(match.group(1))
        unit = match.group(2)
        
        if unit.startswith('d'):
            delta = datetime.timedelta(days=num)
        elif unit.startswith('h'):
            delta = datetime.timedelta(hours=num)
        elif unit.startswith('w'):
            delta = datetime.timedelta(weeks=num)
        elif unit.startswith('mo'):
            delta = datetime.timedelta(days=num * 30)  # przybliżenie
        else:
            delta = datetime.timedelta(days=0)
        
        return (today - delta).isoformat()
    
    # Fallback
    return today.isoformat()


def parse(html):
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    # Dice ma strukturę: każda oferta to link a[href*='/job-detail/']
    # ALE musimy znaleźć cały kontener z metadanymi
    
    # Znajdź wszystkie linki do ofert
    job_links = soup.select("a[href*='/job-detail/']")
    
    print(f"      DEBUG: Znaleziono {len(job_links)} linków do ofert")

    for job_link in job_links:
        try:
            # URL
            href = job_link.get("href")
            if not href:
                continue
                
            if href.startswith("http"):
                full_url = href
            else:
                full_url = "https://www.dice.com" + href

            # Cała karta - szukamy rodzica który zawiera wszystkie dane
            # Zazwyczaj 2-4 poziomy wyżej od linka
            card = job_link.parent
            for _ in range(4):
                if card and card.parent:
                    card = card.parent
                else:
                    break
            
            # TYTUŁ - jest w samym linku job_link
            title = job_link.get_text(strip=True)
            
            if len(title) < 5:
                continue

            if not is_relevant(title):
                continue

            # FIRMA - szukamy w całej karcie
            # Ze screenshota: link z nazwą firmy jest NAD tytułem oferty
            company = ""
            
            # Metoda 1: link do company-profile
            company_links = card.select("a[href*='/company-profile/']") if card else []
            if company_links:
                company = company_links[0].get_text(strip=True)
            
            # Metoda 2: data-wa-click
            if not company and card:
                company_link = card.select_one("a[data-wa-click='djv-job-company-profile-click']")
                if company_link:
                    company = company_link.get_text(strip=True)
            
            # Metoda 3: szukaj tekstu przed tytułem (fallback)
            if not company and card:
                # Wszystkie linki w karcie
                all_links = card.find_all('a', href=True)
                for link in all_links:
                    link_text = link.get_text(strip=True)
                    # Pomijamy linki które są tytułem oferty lub są za krótkie
                    if link_text and link_text != title and len(link_text) > 3:
                        # Jeśli link nie prowadzi do job-detail, to prawdopodobnie firma
                        if '/job-detail/' not in link.get('href', ''):
                            company = link_text
                            break

            # LOKALIZACJA i DATA
            # Ze screenshota: "Remote • Posted 8 days ago • Updated 8 days ago"
            location = "Unknown"
            posted = datetime.date.today().isoformat()
            
            if card:
                # Szukamy tekstu z "Remote", "Posted", "ago"
                card_text = card.get_text()
                
                # Lokalizacja - szukamy "Remote" lub miast
                location_match = re.search(r'(Remote|Hybrid|On-site|[A-Z][a-z]+,\s*[A-Z]{2})', card_text)
                if location_match:
                    location = location_match.group(1).strip()
                
                # Data - szukamy "Posted X days ago"
                date_match = re.search(r'Posted\s+(\d+)\s+(day|hour|week|month)s?\s+ago', card_text, re.IGNORECASE)
                if date_match:
                    posted = parse_posted_date(date_match.group(0))
                elif 'Posted today' in card_text or 'Just posted' in card_text:
                    posted = datetime.date.today().isoformat()
                elif 'Posted yesterday' in card_text:
                    posted = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

            jobs.append({
                "title": title,
                "company": company,
                "location": location,
                "posted": posted,
                "url": full_url,
                "source": "Dice"
            })

        except Exception as e:
            print(f"      ⚠️  Parse error: {e}")
            continue

    return jobs



def run_dice() -> list:
    print("\n── DICE ──────────────────────────────────────")
    all_jobs = []

    for query in DICE_QUERIES:
        print(f"  Szukam: '{query}'...")
        for page in range(1, DICE_MAX_PAGES + 1):
            html = fetch_page(query, page)
            if not html:
                break
            parsed = parse(html)
            if not parsed:
                break
            for j in parsed:
                all_jobs.append({
                    "title":          j["title"],
                    "company":        j.get("company", ""),
                    "location":       j.get("location", "Remote"),
                    "salary":         "",
                    "posted":         j.get("posted", datetime.date.today().isoformat()),
                    "url":            j["url"],
                    "specialization": categorize_job(j["title"], ""),
                    "source":         "Dice",
                    "tags":           "",
                })
            time.sleep(1)

    print(f"  Dice total: {len(all_jobs)} jobów (przed dedup)")
    return all_jobs


# ── MAIN ─────────────────────

def main():
    print("🚀 RemoteEDI.com — Combined Scraper")
    print(f"Start: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")

    jobs = []
    jobs += run_adzuna()
    #jobs += run_jsearch()
    jobs += run_dice()

    print("\nTOTAL:", len(jobs))
    
    # Polacz i deduplikuj
    all_jobs = jobs
    print(f"\nLacznie przed deduplication: {len(all_jobs)}")

    unique = deduplicate(all_jobs)
    print(f"Po deduplication: {len(unique)}")
    
    keys = ["title","company","location","salary", "posted","url","specialization", "source", "tags"]

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(unique)


if __name__ == "__main__":
    main()