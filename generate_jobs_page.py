"""
RemoteEDI.com — Generator strony z jobami
==========================================
Czyta edi_jobs_all.csv i generuje jobs.html

Uruchomienie:
    py generate_jobs_page.py

Wyjscie:
    jobs.html  (wrzuc do repo GitHub obok index.html)
"""

import csv
import datetime
import os

CSV_FILE   = "edi_jobs_all.csv"
OUTPUT_FILE = "jobs.html"

# ── Czytanie CSV ──────────────────────────────────────────────────────────────

def load_jobs(filename: str) -> list:
    if not os.path.exists(filename):
        print(f"Brak pliku {filename} — uruchom najpierw scraper_combined.py")
        return []

    jobs = []
    with open(filename, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            jobs.append(row)

    # Sortuj po dacie — najnowsze pierwsze
    jobs.sort(key=lambda j: j.get("posted", ""), reverse=True)
    return jobs


def format_date(iso_date: str) -> str:
    """2026-03-10 -> Mar 10, 2026"""
    try:
        dt = datetime.date.fromisoformat(iso_date)
        return dt.strftime("%b %d, %Y")
    except:
        return iso_date


def region_from_location(location: str) -> str:
    """Zwraca region do filtrowania."""
    loc = location.upper()
    if "USA" in loc or "US" in loc:
        return "USA"
    elif "UK" in loc or "UNITED KINGDOM" in loc:
        return "UK"
    elif "CANADA" in loc or "CA" in loc:
        return "Canada"
    elif "AUSTRALIA" in loc or "AU" in loc:
        return "Australia"
    elif "GERMANY" in loc or "DE" in loc:
        return "Germany"
    elif "INDIA" in loc or " IN" in loc:
        return "India"
    elif "PHILIPPINES" in loc or " PH" in loc:
        return "Philippines"
    elif "SPAIN" in loc or " ES" in loc:
        return "Spain"
    else:
        return "Global"


def spec_color(spec: str) -> str:
    """Kolor tagu specjalizacji."""
    colors = {
        "Healthcare EDI":    "#00b894",
        "EDI Developer":     "#0984e3",
        "EDI Analyst":       "#6c5ce7",
        "SAP EDI":           "#e17055",
        "Logistics & Retail":"#fdcb6e",
        "EDI Coordinator":   "#fd79a8",
        "EDI General":       "#636e72",
    }
    return colors.get(spec, "#636e72")


# ── Generator HTML ────────────────────────────────────────────────────────────

def generate_html(jobs: list) -> str:
    today = datetime.date.today().strftime("%B %d, %Y")
    total = len(jobs)

    # Zbierz unikalne wartosci filtrow
    specs    = sorted(set(j["specialization"] for j in jobs if j["specialization"]))
    regions  = sorted(set(region_from_location(j["location"]) for j in jobs))

    # Generuj karty
    cards_html = ""
    for job in jobs:
        region = region_from_location(job["location"])
        color  = spec_color(job["specialization"])
        date   = format_date(job["posted"])
        salary = job.get("salary", "")
        source = job.get("source", "")

        salary_html = f'<span class="salary">{salary}</span>' if salary else ""
        source_html = f'<span class="job-source">{source}</span>' if source else ""

        # Data attributes dla filtrowania JS
        cards_html += f"""
        <div class="job-card"
             data-spec="{job['specialization']}"
             data-region="{region}"
             data-search="{job['title'].lower()} {job['company'].lower()} {job['specialization'].lower()}">
          <div class="card-header">
            <span class="spec-tag" style="background:{color}20; color:{color}; border-color:{color}40">{job['specialization']}</span>
            <span class="job-date">{date}</span>
          </div>
          <h3 class="job-title">{job['title']}</h3>
          <div class="job-company">{job['company']}</div>
          <div class="job-meta">
            <span class="job-location">📍 {job['location']}</span>
            {salary_html}
          </div>
          <div class="card-footer">
            {source_html}
            <a href="{job['url']}" target="_blank" rel="noopener" class="apply-btn">Apply →</a>
          </div>
        </div>"""

    # Opcje filtrow
    spec_options = "\n".join(f'<option value="{s}">{s}</option>' for s in specs)
    region_options = "\n".join(f'<option value="{r}">{r}</option>' for r in regions)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Remote EDI Jobs — {total} Open Positions | RemoteEDI.com</title>
  <meta name="description" content="Browse {total} remote EDI jobs. Curated daily from top job boards. Healthcare EDI, SAP, logistics, and more.">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    :root {{
      --bg:        #0b0f0e;
      --bg2:       #111614;
      --bg3:       #1a1f1e;
      --accent:    #00e5a0;
      --accent2:   #00b87a;
      --text:      #e8ede9;
      --muted:     #7a8c82;
      --border:    #1e2926;
      --card-bg:   #131817;
      --radius:    10px;
    }}

    body {{
      background: var(--bg);
      color: var(--text);
      font-family: 'DM Sans', sans-serif;
      min-height: 100vh;
    }}

    /* ── NAV ── */
    nav {{
      border-bottom: 1px solid var(--border);
      padding: 0 2rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      height: 60px;
      position: sticky;
      top: 0;
      background: var(--bg);
      z-index: 100;
    }}
    .nav-logo {{
      font-family: 'IBM Plex Mono', monospace;
      font-size: 1rem;
      color: var(--accent);
      text-decoration: none;
    }}
    .nav-logo span {{ color: var(--muted); }}
    .nav-links {{ display: flex; gap: 1.5rem; align-items: center; }}
    .nav-links a {{
      color: var(--muted);
      text-decoration: none;
      font-size: 0.9rem;
      transition: color 0.2s;
    }}
    .nav-links a:hover {{ color: var(--text); }}
    .nav-cta {{
      background: var(--accent);
      color: #000 !important;
      padding: 0.4rem 1rem;
      border-radius: 6px;
      font-weight: 600;
      font-size: 0.85rem !important;
    }}

    /* ── HERO ── */
    .page-hero {{
      padding: 3rem 2rem 2rem;
      max-width: 1100px;
      margin: 0 auto;
    }}
    .page-hero h1 {{
      font-size: clamp(1.6rem, 3vw, 2.2rem);
      font-weight: 600;
      line-height: 1.2;
      margin-bottom: 0.5rem;
    }}
    .page-hero h1 em {{
      color: var(--accent);
      font-style: normal;
      font-family: 'IBM Plex Mono', monospace;
    }}
    .page-hero p {{
      color: var(--muted);
      font-size: 0.95rem;
    }}
    .updated {{
      font-family: 'IBM Plex Mono', monospace;
      font-size: 0.75rem;
      color: var(--muted);
      margin-top: 0.75rem;
    }}
    .updated span {{ color: var(--accent); }}

    /* ── FILTERS ── */
    .filters {{
      max-width: 1100px;
      margin: 0 auto;
      padding: 0 2rem 1.5rem;
      display: flex;
      gap: 0.75rem;
      flex-wrap: wrap;
      align-items: center;
    }}
    .search-box {{
      flex: 1;
      min-width: 200px;
      background: var(--bg3);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 0.6rem 1rem;
      color: var(--text);
      font-family: 'DM Sans', sans-serif;
      font-size: 0.9rem;
      outline: none;
      transition: border-color 0.2s;
    }}
    .search-box:focus {{ border-color: var(--accent); }}
    .search-box::placeholder {{ color: var(--muted); }}

    select {{
      background: var(--bg3);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 0.6rem 1rem;
      color: var(--text);
      font-family: 'DM Sans', sans-serif;
      font-size: 0.85rem;
      outline: none;
      cursor: pointer;
      transition: border-color 0.2s;
    }}
    select:focus {{ border-color: var(--accent); }}

    .results-count {{
      font-family: 'IBM Plex Mono', monospace;
      font-size: 0.8rem;
      color: var(--muted);
      margin-left: auto;
      white-space: nowrap;
    }}
    .results-count span {{ color: var(--accent); }}

    /* ── GRID ── */
    .jobs-grid {{
      max-width: 1100px;
      margin: 0 auto;
      padding: 0 2rem 4rem;
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 1rem;
    }}

    /* ── CARD ── */
    .job-card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 1.25rem;
      display: flex;
      flex-direction: column;
      gap: 0.6rem;
      transition: border-color 0.2s, transform 0.15s;
    }}
    .job-card:hover {{
      border-color: #2a3530;
      transform: translateY(-2px);
    }}
    .job-card.hidden {{ display: none; }}

    .card-header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 0.5rem;
    }}

    .spec-tag {{
      font-size: 0.72rem;
      font-weight: 600;
      padding: 0.25rem 0.6rem;
      border-radius: 4px;
      border: 1px solid;
      font-family: 'IBM Plex Mono', monospace;
      white-space: nowrap;
    }}

    .job-date {{
      font-size: 0.75rem;
      color: var(--muted);
      font-family: 'IBM Plex Mono', monospace;
      white-space: nowrap;
    }}

    .job-title {{
      font-size: 1rem;
      font-weight: 600;
      line-height: 1.3;
      color: var(--text);
    }}

    .job-company {{
      font-size: 0.85rem;
      color: var(--muted);
    }}

    .job-meta {{
      display: flex;
      gap: 1rem;
      align-items: center;
      flex-wrap: wrap;
    }}

    .job-location {{
      font-size: 0.8rem;
      color: var(--muted);
    }}

    .salary {{
      font-family: 'IBM Plex Mono', monospace;
      font-size: 0.8rem;
      color: var(--accent);
      font-weight: 500;
    }}

    .card-footer {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: auto;
      padding-top: 0.5rem;
      border-top: 1px solid var(--border);
    }}

    .job-source {{
      font-size: 0.72rem;
      color: var(--muted);
      font-family: 'IBM Plex Mono', monospace;
    }}

    .apply-btn {{
      background: transparent;
      border: 1px solid var(--accent);
      color: var(--accent);
      padding: 0.35rem 0.9rem;
      border-radius: 6px;
      font-size: 0.82rem;
      font-weight: 600;
      text-decoration: none;
      transition: background 0.2s, color 0.2s;
      font-family: 'IBM Plex Mono', monospace;
    }}
    .apply-btn:hover {{
      background: var(--accent);
      color: #000;
    }}

    /* ── EMPTY STATE ── */
    .empty-state {{
      grid-column: 1/-1;
      text-align: center;
      padding: 4rem 2rem;
      color: var(--muted);
    }}
    .empty-state h3 {{ font-size: 1.2rem; margin-bottom: 0.5rem; color: var(--text); }}

    /* ── FOOTER ── */
    footer {{
      border-top: 1px solid var(--border);
      padding: 2rem;
      text-align: center;
      color: var(--muted);
      font-size: 0.82rem;
    }}
    footer a {{ color: var(--accent); text-decoration: none; }}

    @media (max-width: 600px) {{
      .filters {{ padding: 0 1rem 1rem; }}
      .jobs-grid {{ padding: 0 1rem 3rem; grid-template-columns: 1fr; }}
      .page-hero {{ padding: 2rem 1rem 1rem; }}
      nav {{ padding: 0 1rem; }}
    }}
  </style>
</head>
<body>

<nav>
  <a href="/" class="nav-logo">r<span>EDI</span>.com</a>
  <div class="nav-links">
    <a href="/">Home</a>
    <a href="/jobs.html">Jobs</a>
    <a href="/#pricing">Post a Job</a>
    <a href="/#waitlist" class="nav-cta">Get Alerts</a>
  </div>
</nav>

<div class="page-hero">
  <h1>Remote <em>EDI Jobs</em><br>Curated Daily</h1>
  <p>Aggregated from LinkedIn, Indeed, Glassdoor and more. Updated every morning.</p>
  <p class="updated">Last updated: <span>{today}</span> &nbsp;·&nbsp; <span>{total}</span> open positions</p>
</div>

<div class="filters">
  <input type="text" class="search-box" id="searchBox" placeholder="Search title, company..." oninput="filterJobs()">
  <select id="specFilter" onchange="filterJobs()">
    <option value="">All Specializations</option>
    {spec_options}
  </select>
  <select id="regionFilter" onchange="filterJobs()">
    <option value="">All Regions</option>
    {region_options}
  </select>
  <div class="results-count" id="resultsCount"><span>{total}</span> jobs</div>
</div>

<div class="jobs-grid" id="jobsGrid">
  {cards_html}
  <div class="empty-state" id="emptyState" style="display:none">
    <h3>No jobs found</h3>
    <p>Try adjusting your filters or search term.</p>
  </div>
</div>

<footer>
  <p>© 2026 RemoteEDI.com &nbsp;·&nbsp; <a href="mailto:hire@remoteedi.com">hire@remoteedi.com</a> &nbsp;·&nbsp; <a href="/#pricing">Post a Job — $199</a></p>
</footer>

<script>
  function filterJobs() {{
    const search  = document.getElementById('searchBox').value.toLowerCase();
    const spec    = document.getElementById('specFilter').value;
    const region  = document.getElementById('regionFilter').value;

    const cards = document.querySelectorAll('.job-card');
    let visible = 0;

    cards.forEach(card => {{
      const matchSearch = !search || card.dataset.search.includes(search);
      const matchSpec   = !spec   || card.dataset.spec === spec;
      const matchRegion = !region || card.dataset.region === region;

      if (matchSearch && matchSpec && matchRegion) {{
        card.classList.remove('hidden');
        visible++;
      }} else {{
        card.classList.add('hidden');
      }}
    }});

    document.getElementById('resultsCount').innerHTML = `<span>${{visible}}</span> jobs`;
    document.getElementById('emptyState').style.display = visible === 0 ? 'block' : 'none';
  }}
</script>

</body>
</html>"""


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("RemoteEDI.com — Generator strony z jobami")
    print(f"Czytam: {CSV_FILE}")

    jobs = load_jobs(CSV_FILE)
    if not jobs:
        return

    print(f"Zaladowano {len(jobs)} jobów")

    html = generate_html(jobs)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Wygenerowano: {OUTPUT_FILE}")
    print(f"Wrzuc do repo GitHub obok index.html")
    print(f"Netlify automatycznie opublikuje na remoteedi.com/jobs.html")


if __name__ == "__main__":
    main()
