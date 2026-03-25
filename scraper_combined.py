import requests
import csv
import datetime
import time
import os
import json
from bs4 import BeautifulSoup

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
                "posted": datetime.date.today().isoformat(),
                "url": j.get("job_apply_link"),
                "source": "JSearch",
                "specialization": categorize_job(title, j.get("job_description", ""))
            })



    except Exception as e:
        print("JSearch error:", e)

    print("JSearch:", len(jobs))
    return jobs


# ── DICE (SPRAWDZONA WERSJA) ─────────────────────

def run_dice():
    print("\n── DICE ──")
    jobs = []

    for page in range(1, 4):
        url = f"https://www.dice.com/jobs/q-edi+remote-jobs?page={page}"

        try:
            r = requests.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept-Language": "en-US,en;q=0.9"
                },
                timeout=30
            )

            soup = BeautifulSoup(r.text, "html.parser")

            # 🔥 TRY 1: cards
            cards = soup.select("div.card")

            if cards:
                print(f"page {page}: {len(cards)} cards")

                for card in cards:
                    try:
                        title_el = card.select_one("a.card-title-link")
                        if not title_el:
                            continue

                        title = title_el.text.strip()
                        if not is_edi(title):
                            continue

                        href = title_el.get("href")
                        if not href:
                            continue

                        url = href if href.startswith("http") else "https://www.dice.com" + href

                        company_el = card.select_one(".card-company")
                        company = company_el.text.strip() if company_el else ""

                        location_el = card.select_one(".card-location")
                        location = location_el.text.strip() if location_el else "Remote"

                        salary_el = card.select_one(".card-salary")
                        salary = salary_el.text.strip() if salary_el else ""

                        tags = ",".join([k for k in ["edi","sap","boomi","mulesoft","x12","edifact"] if k in title.lower()])

                        jobs.append({
                            "title": title,
                            "company": company,
                            "location": location,
                            "salary": salary,
                            "posted": datetime.date.today().isoformat(),
                            "url": url,
                            "specialization": categorize_job(title, ""),
                            "source": "Dice",
                            "tags": tags
                        })

                    except:
                        continue

            else:
                # 🔥 FALLBACK: link-only parsing
                links = soup.select("a[href*='/job-detail/']")
                print(f"page {page}: fallback {len(links)} links")

                if not links:
                    break

                for l in links:
                    try:
                        title = l.text.strip()
                        if not is_edi(title):
                            continue

                        href = l.get("href")
                        if not href:
                            continue

                        url = href if href.startswith("http") else "https://www.dice.com" + href

                        tags = ",".join([k for k in ["edi","sap","boomi","mulesoft","x12","edifact"] if k in title.lower()])

                        jobs.append({
                            "title": title,
                            "company": "",
                            "location": "Remote",
                            "salary": "",
                            "posted": datetime.date.today().isoformat(),
                            "url": url,
                            "specialization": categorize_job(title, ""),
                            "source": "Dice",
                            "tags": tags
                        })

                    except:
                        continue

            time.sleep(1)

        except Exception as e:
            print("Dice error:", e)

    print("Dice:", len(jobs))
    return jobs


# ── MAIN ─────────────────────

def main():
    print("🚀 RemoteEDI.com — Combined Scraper")
    print(f"Start: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")

    jobs = []
    jobs += run_adzuna()
    #jobs += run_jsearch()
    jobs += run_dice()

    print("\nTOTAL:", len(jobs))

    keys = ["title","company","location","salary", "posted","url","specialization", "source", "tags"]

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(jobs)


if __name__ == "__main__":
    main()