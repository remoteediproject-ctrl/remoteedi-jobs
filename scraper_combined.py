"""
EDI Jobs Scraper — Combined (Adzuna + JSearch)
================================================
Agreguje remote EDI joby z wielu zrodel globalnie.

Zrodla:
  - Adzuna API  (US, UK, CA, AU, DE)
  - JSearch API (Indeed, LinkedIn, Glassdoor - global)

Uruchomienie:
    py scraper_combined.py

Wyjscie:
    edi_jobs_all.csv
"""

import requests
import csv
import datetime
import time
import re

# ── Klucze API ───────────────────────────────────────────────────────────────

import os

ADZUNA_APP_ID  = os.environ.get("ADZUNA_APP_ID",  "03049e54")
ADZUNA_APP_KEY = os.environ.get("ADZUNA_APP_KEY", "03494e483e28beff7d8ee54573bac109")
JSEARCH_KEY    = os.environ.get("JSEARCH_KEY",    "fd093a3128msh485b2b1ce1651c6p108b94jsn4e84230e71cc")

OUTPUT_FILE = "edi_jobs_all.csv"

# ── Helpery ───────────────────────────────────────────────────────────────────

def is_real_edi_job(title: str) -> bool:
    t = title.lower()
    for term in ["edi ", " edi", "/edi", "edi/", "electronic data interchange", "x12", "edifact", "idoc"]:
        if term in t:
            return True
    return False


def categorize_job(title: str, description: str) -> str:
    text = (title + " " + description).lower()
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


# ════════════════════════════════════════════════════════════════════════════
# JSEARCH SCRAPER
# ════════════════════════════════════════════════════════════════════════════

JSEARCH_QUERIES = [
    "EDI analyst remote",
    "EDI developer remote",
    "EDI specialist remote",
    "EDI engineer remote",
    "EDI coordinator remote",
    "electronic data interchange remote",
    "EDI analyst remote Europe",
    "EDI specialist remote India",
    "EDI developer remote Philippines",
    "EDI developer remote Canada",
    "EDI developer remote Australia",
]

def fetch_jsearch(query: str) -> list:
    params = {
        "query":            query,
        "page":             1,
        "num_pages":        1,
        "date_posted":      "month",
        "remote_jobs_only": "true",
    }
    headers = {
        "X-RapidAPI-Key":  JSEARCH_KEY,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
    }
    try:
        r = requests.get(
            "https://jsearch.p.rapidapi.com/search",
            headers=headers, params=params, timeout=30
        )
        r.raise_for_status()
        return r.json().get("data", [])
    except Exception as e:
        print(f"    x Blad: {e}")
        return []


def parse_jsearch_job(job: dict) -> dict:
    title   = job.get("job_title", "").strip()
    company = job.get("employer_name", "").strip()
    url     = job.get("job_apply_link") or job.get("job_url", "")
    desc    = job.get("job_description", "")
    city    = job.get("job_city") or ""
    state   = job.get("job_state") or ""
    country = job.get("job_country") or ""
    is_remote = job.get("job_is_remote", False)

    if not is_real_edi_job(title):
        return None

    # Wyklucz aggregatory ktore duplikuja oferty
    aggregators = ["jobgether", "jooble", "talent.com", "jobrapido", "neuvoo", "findadatajob"]
    if any(a in company.lower() for a in aggregators):
        return None

    # Wyklucz onsite/hybrid
    title_lower = title.lower()
    if any(x in title_lower for x in ["onsite", "on-site", "on site", "hybrid", "in-office"]):
        return None

    # Lokalizacja
    if is_remote:
        if country in ("US", "USA"):
            location = "Remote USA"
        elif country:
            location = f"Remote {country}"
        else:
            location = "Remote"
    elif city and state:
        location = f"{city}, {state}"
    elif country:
        location = f"Remote {country}"
    else:
        location = "Remote"

    # Salary z poprawna waluta
    s_min   = job.get("job_min_salary")
    s_max   = job.get("job_max_salary")
    period  = (job.get("job_salary_period") or "").upper()
    curr    = (job.get("job_salary_currency") or "USD").upper()
    symbol  = {"USD": "$", "GBP": "£", "EUR": "€", "CAD": "CA$", "AUD": "A$"}.get(curr, "$")
    suffix  = "/hr" if period == "HOUR" else "/yr"
    if s_min and s_max and s_min != s_max:
        if period == "HOUR":
            salary = f"{symbol}{s_min:.0f} - {symbol}{s_max:.0f}{suffix}"
        else:
            salary = f"{symbol}{int(s_min):,} - {symbol}{int(s_max):,}{suffix}"
    elif s_min:
        salary = f"{symbol}{int(s_min):,}+{suffix}"
    else:
        salary = ""

    # Data
    posted_at = job.get("job_posted_at_datetime_utc", "")
    try:
        dt = datetime.datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
        posted = dt.date().isoformat()
    except:
        posted = datetime.date.today().isoformat()

    return {
        "title":          title,
        "company":        company,
        "location":       location,
        "salary":         salary,
        "posted":         posted,
        "url":            url,
        "specialization": categorize_job(title, desc),
        "source":         job.get("job_publisher", "JSearch"),
        "tags":           "",
    }


def run_jsearch() -> list:
    print("\n── JSEARCH ─────────────────────────────────────")
    all_jobs = []

    for query in JSEARCH_QUERIES:
        print(f"  Szukam: '{query}'...")
        results = fetch_jsearch(query)
        print(f"    -> {len(results)} wynikow")
        for r in results:
            job = parse_jsearch_job(r)
            if job:
                all_jobs.append(job)
        time.sleep(1)

    print(f"\n  JSearch total: {len(all_jobs)} jobów (przed dedup)")
    return all_jobs


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

def save_to_csv(jobs: list, filename: str) -> None:
    if not jobs:
        print("Brak jobow do zapisania")
        return
    fieldnames = ["title", "company", "location", "salary", "posted", "url", "specialization", "source", "tags"]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(jobs)
    print(f"\nZapisano {len(jobs)} jobow do {filename}")


def print_summary(jobs: list) -> None:
    from collections import Counter
    print("\n" + "="*55)
    print(f"LACZNA LICZBA EDI JOBOW: {len(jobs)}")
    print("="*55)

    print("\nPO SPECJALIZACJI:")
    for spec, count in Counter(j["specialization"] for j in jobs).most_common():
        print(f"  {spec}: {count}")

    print("\nPO LOKALIZACJI:")
    for loc, count in Counter(j["location"] for j in jobs).most_common(10):
        print(f"  {loc}: {count}")

    print("\nPO ZRODLE:")
    for src, count in Counter(j["source"] for j in jobs).most_common():
        print(f"  {src}: {count}")

    print("\nPRZYKLADY:")
    for job in jobs[:5]:
        print(f"\n  [{job['specialization']}] {job['location']}")
        print(f"  {job['title']} @ {job['company']}")
        print(f"  {job['salary'] or 'brak salary'} | {job['posted']}")


def main():
    print("RemoteEDI.com — Combined Scraper")
    print(f"Start: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # Uruchom oba scrapers
    adzuna_jobs  = run_adzuna()
    jsearch_jobs = run_jsearch()

    # Polacz i deduplikuj
    all_jobs = adzuna_jobs + jsearch_jobs
    print(f"\nLacznie przed deduplication: {len(all_jobs)}")

    unique = deduplicate(all_jobs)
    print(f"Po deduplication: {len(unique)}")

    # Zapisz i pokaz
    save_to_csv(unique, OUTPUT_FILE)
    print_summary(unique)

    print(f"\nGotowe! Plik: {OUTPUT_FILE}")
    print(f"Czas: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")


if __name__ == "__main__":
    main()
