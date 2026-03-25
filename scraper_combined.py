import requests
import csv
import datetime
import time
import os
import smtplib
import json
from email.mime.text import MIMEText
from bs4 import BeautifulSoup

# ── API KEYS ─────────────────────

ADZUNA_APP_ID  = os.environ.get("ADZUNA_APP_ID",  "03049e54")
ADZUNA_APP_KEY = os.environ.get("ADZUNA_APP_KEY", "03494e483e28beff7d8ee54573bac109")
JSEARCH_KEY    = os.environ.get("JSEARCH_KEY",    "fd093a3128msh485b2b1ce1651c6p108b94jsn4e84230e71cc")

OUTPUT_FILE = "edi_jobs_all.csv"
CACHE_FILE = "jsearch_cache.json"

# ── EMAIL CONFIG ─────────────────────
EMAIL = os.environ.get("EMAIL", "")
EMAIL_PASS = os.environ.get("EMAIL_PASS", "")

# ── HELPERS ─────────────────────

def is_real_edi_job(title: str) -> bool:
    t = title.lower()
    return any(x in t for x in ["edi", "x12", "edifact", "idoc"])


# ── CACHE ─────────────────────

def load_cache():
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)


# ── SAFE REQUEST ─────────────────────

def safe_request(url, headers=None, params=None):
    for attempt in range(3):
        try:
            r = requests.get(url, headers=headers, params=params, timeout=30)

            if r.status_code == 401:
                print("    ❌ 401 Unauthorized")
                return None

            if r.status_code == 429:
                wait = 2 ** attempt
                print(f"    ⚠️ 429 → retry in {wait}s")
                time.sleep(wait)
                continue

            r.raise_for_status()
            return r

        except Exception as e:
            print(f"    x Error: {e}")
            time.sleep(2)

    return None


# ── ADZUNA ─────────────────────

def run_adzuna():
    print("\n── ADZUNA ──")
    jobs = []

    queries = ["EDI analyst", "EDI developer"]

    for q in queries:
        url = "https://api.adzuna.com/v1/api/jobs/us/search/1"

        params = {
            "app_id": ADZUNA_APP_ID,
            "app_key": ADZUNA_APP_KEY,
            "what": q,
            "results_per_page": 20,
        }

        r = safe_request(url, params=params)
        if not r:
            continue

        results = r.json().get("results", [])

        for job in results:
            title = job.get("title", "")
            if not is_real_edi_job(title):
                continue

            jobs.append({
                "title": title,
                "company": job.get("company", {}).get("display_name", ""),
                "location": "Remote USA",
                "posted": datetime.date.today().isoformat(),
                "url": job.get("redirect_url", ""),
                "source": "Adzuna"
            })

        time.sleep(1)

    print(f"  Adzuna jobs: {len(jobs)}")
    return jobs


# ── JSEARCH ─────────────────────

JSEARCH_QUERIES = [
    "EDI analyst remote",
    "EDI developer remote",
    "EDI specialist remote",
]

def fetch_jsearch(query: str) -> list:
    url = "https://jsearch.p.rapidapi.com/search"

    headers = {
        "X-RapidAPI-Key": JSEARCH_KEY,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
    }

    params = {
        "query": query,
        "page": 1,
        "num_pages": 1,
        "date_posted": "month",
        "remote_jobs_only": "true",
    }

    r = safe_request(url, headers=headers, params=params)

    if not r:
        return []

    try:
        return r.json().get("data", [])
    except:
        return []


def parse_jsearch_job(job: dict) -> dict:
    title = job.get("job_title", "")
    if not is_real_edi_job(title):
        return None

    return {
        "title": title,
        "company": job.get("employer_name", ""),
        "location": "Remote",
        "posted": datetime.date.today().isoformat(),
        "url": job.get("job_apply_link") or "",
        "source": "JSearch"
    }


def run_jsearch():
    print("\n── JSEARCH ──")
    jobs = []

    cache = load_cache()
    today = datetime.date.today().isoformat()

    for query in JSEARCH_QUERIES:
        print(f"  → {query}")

        if query in cache and cache[query]["date"] == today:
            results = cache[query]["data"]
            print("    (cache hit)")
        else:
            results = fetch_jsearch(query)
            cache[query] = {
                "date": today,
                "data": results
            }
            save_cache(cache)

        print(f"    {len(results)} wyników")

        for r in results:
            job = parse_jsearch_job(r)
            if job:
                jobs.append(job)

        time.sleep(1)

    print(f"  JSearch jobs: {len(jobs)}")
    return jobs


# ── DICE (FIXED) ─────────────────────

DICE_QUERIES = ["edi+remote"]
MAX_PAGES = 5


def run_dice():
    print("\n── DICE ──")

    jobs = []

    for query in DICE_QUERIES:
        print(f"  → {query}")

        for page in range(1, MAX_PAGES + 1):
            print(f"     page {page}")

            url = f"https://www.dice.com/jobs/q-{query}-jobs?page={page}"

            try:
                r = requests.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0",
                        "Accept-Language": "en-US,en;q=0.9"
                    },
                    timeout=30
                )

                print(f"     status: {r.status_code}")

                if r.status_code != 200:
                    break

                soup = BeautifulSoup(r.text, "html.parser")

                cards = soup.select("div.card") or soup.select("a[href*='/job-detail/']")

                print(f"     cards: {len(cards)}")

                if len(cards) == 0:
                    print("     ⛔ stop")
                    break

                for card in cards:
                    try:
                        title_el = card.select_one("a.card-title-link") if "card" in (card.get("class") or []) else card

                        title = title_el.text.strip()

                        if not is_real_edi_job(title):
                            continue

                        href = title_el.get("href")
                        if not href:
                            continue

                        full_url = href if href.startswith("http") else "https://www.dice.com" + href

                        jobs.append({
                            "title": title,
                            "company": "",
                            "location": "Remote",
                            "posted": datetime.date.today().isoformat(),
                            "url": full_url,
                            "source": "Dice"
                        })

                    except:
                        continue

                time.sleep(1)

            except Exception as e:
                print("     ❌ error:", e)
                break

    print(f"  Dice jobs: {len(jobs)}")
    return jobs


# ── DEDUP ─────────────────────

def deduplicate(jobs):
    seen = set()
    unique = []

    for j in jobs:
        key = j["url"]

        if key in seen:
            continue

        seen.add(key)
        unique.append(j)

    return unique


# ── CSV ─────────────────────

def save_csv(jobs):
    keys = ["title", "company", "location", "posted", "url", "source"]

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(jobs)


# ── EMAIL ─────────────────────

def send_email(summary):
    if not EMAIL or not EMAIL_PASS:
        print("📭 Email skipped (no config)")
        return

    msg = MIMEText(summary)
    msg["Subject"] = "EDI Scraper Report"
    msg["From"] = EMAIL
    msg["To"] = EMAIL

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL, EMAIL_PASS)
            server.send_message(msg)
        print("📧 Email sent")
    except Exception as e:
        print("❌ Email error:", e)


# ── MAIN ─────────────────────

def main():
    print("🚀 RemoteEDI Scraper")

    adzuna_jobs = run_adzuna()
    jsearch_jobs = run_jsearch()
    dice_jobs = run_dice()

    all_jobs = adzuna_jobs + jsearch_jobs + dice_jobs
    final_jobs = deduplicate(all_jobs)

    print(f"\nTOTAL RAW: {len(all_jobs)}")
    print(f"TOTAL UNIQUE: {len(final_jobs)}")

    save_csv(final_jobs)

    summary = f"""
EDI SCRAPER REPORT

Total unique jobs: {len(final_jobs)}
Adzuna: {len(adzuna_jobs)}
JSearch: {len(jsearch_jobs)}
Dice: {len(dice_jobs)}

Time: {datetime.datetime.now()}
"""

    send_email(summary)


if __name__ == "__main__":
    main()