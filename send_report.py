"""
RemoteEDI.com — Raport monitoringu
====================================
Porownuje nowe joby z previously seen, wysyla raport na Twoj email.
Uruchamiany przez GitHub Actions po scraper_combined.py

Wymaga zmiennych srodowiskowych:
  MAILERLITE_KEY  — klucz API MailerLite
  REPORT_EMAIL    — Twoj email (gdzie dostaniesz raport)
"""

import csv
import json
import os
import datetime
import requests

# ── Config ────────────────────────────────────────────────────────────────────

CSV_FILE       = "edi_jobs_all.csv"
SEEN_FILE      = "seen_jobs.json"
MAILERLITE_KEY = os.environ.get("MAILERLITE_KEY", "")
REPORT_EMAIL   = os.environ.get("REPORT_EMAIL", "")

# ── Load jobs ─────────────────────────────────────────────────────────────────

def load_csv(filename: str) -> list:
    if not os.path.exists(filename):
        return []
    with open(filename, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_seen() -> set:
    """Wczytuje zbior wczesniej widzianych job ID."""
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return set(data.get("seen_ids", []))


def save_seen(seen_ids: set) -> None:
    """Zapisuje zbior widzianych job ID."""
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "seen_ids":   list(seen_ids),
            "updated_at": datetime.datetime.utcnow().isoformat()
        }, f, indent=2)


def job_id(job: dict) -> str:
    """Unikalny identyfikator joba — tytu + firma."""
    return f"{job['title'].lower().strip()}|{job['company'].lower().strip()}"


# ── Compare ───────────────────────────────────────────────────────────────────

def find_new_jobs(jobs: list, seen_ids: set) -> list:
    """Zwraca joby ktore nie byly wczesniej widziane."""
    new = []
    for job in jobs:
        jid = job_id(job)
        if jid not in seen_ids:
            new.append(job)
    return new


# ── Email report ──────────────────────────────────────────────────────────────

def send_report(total: int, new_jobs: list, errors: list) -> None:
    """Wysyla raport monitoringu przez MailerLite transactional email."""

    if not MAILERLITE_KEY or not REPORT_EMAIL:
        print("Brak MAILERLITE_KEY lub REPORT_EMAIL — pomijam wyslanie raportu")
        return

    today = datetime.date.today().strftime("%Y-%m-%d")
    new_count = len(new_jobs)

    # Tabela nowych jobow (max 20)
    rows = ""
    for job in new_jobs[:20]:
        salary = job.get("salary", "") or "—"
        rows += f"""
        <tr>
          <td style="padding:6px 8px;border-bottom:1px solid #1e2926">{job['title']}</td>
          <td style="padding:6px 8px;border-bottom:1px solid #1e2926;color:#7a8c82">{job['company']}</td>
          <td style="padding:6px 8px;border-bottom:1px solid #1e2926;color:#00e5a0;font-family:monospace">{salary}</td>
          <td style="padding:6px 8px;border-bottom:1px solid #1e2926;color:#7a8c82">{job['location']}</td>
          <td style="padding:6px 8px;border-bottom:1px solid #1e2926;color:#7a8c82">{job['specialization']}</td>
        </tr>"""

    if new_count > 20:
        rows += f'<tr><td colspan="5" style="padding:8px;color:#7a8c82;text-align:center">... i {new_count - 20} wiecej</td></tr>'

    errors_html = ""
    if errors:
        errors_html = f'<p style="color:#e17055;margin-top:1rem">⚠ Bledy: {", ".join(errors)}</p>'

    if new_count == 0:
        jobs_section = '<p style="color:#7a8c82;text-align:center;padding:1rem">No new jobs today.</p>'
    else:
        shown = min(new_count, 20)
        jobs_section = f'''
      <div style="font-size:0.9rem;color:#7a8c82;margin-bottom:0.75rem">New jobs ({shown} shown):</div>
      <table style="width:100%;border-collapse:collapse;font-size:0.82rem;background:#111614;border-radius:8px;overflow:hidden">
        <thead>
          <tr style="color:#7a8c82;font-size:0.75rem">
            <th style="padding:8px;text-align:left;border-bottom:1px solid #1e2926">Title</th>
            <th style="padding:8px;text-align:left;border-bottom:1px solid #1e2926">Company</th>
            <th style="padding:8px;text-align:left;border-bottom:1px solid #1e2926">Salary</th>
            <th style="padding:8px;text-align:left;border-bottom:1px solid #1e2926">Location</th>
            <th style="padding:8px;text-align:left;border-bottom:1px solid #1e2926">Type</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
      '''

    html_body = f"""
    <div style="background:#0b0f0e;color:#e8ede9;font-family:'DM Sans',sans-serif;padding:2rem;max-width:700px;margin:0 auto">
      <div style="font-family:monospace;color:#00e5a0;font-size:1.1rem;margin-bottom:1.5rem">
        rEDI.com — Daily Scraper Report
      </div>

      <table style="width:100%;border-collapse:collapse;margin-bottom:1.5rem;background:#111614;border-radius:8px;overflow:hidden">
        <tr>
          <td style="padding:1rem;border-right:1px solid #1e2926;text-align:center">
            <div style="font-size:2rem;font-weight:700;color:#00e5a0">{total}</div>
            <div style="color:#7a8c82;font-size:0.85rem">total jobs</div>
          </td>
          <td style="padding:1rem;border-right:1px solid #1e2926;text-align:center">
            <div style="font-size:2rem;font-weight:700;color:#{'00e5a0' if new_count > 0 else '7a8c82'}">{new_count}</div>
            <div style="color:#7a8c82;font-size:0.85rem">new today</div>
          </td>
          <td style="padding:1rem;text-align:center">
            <div style="font-size:1rem;font-weight:600;color:#e8ede9">{today}</div>
            <div style="color:#7a8c82;font-size:0.85rem">run date</div>
          </td>
        </tr>
      </table>

      {jobs_section}

      {errors_html}

      <div style="margin-top:2rem;padding-top:1rem;border-top:1px solid #1e2926">
        <a href="https://remoteedi.com/jobs.html"
           style="background:#00e5a0;color:#000;padding:0.5rem 1.25rem;border-radius:6px;text-decoration:none;font-weight:600;font-size:0.85rem">
          View Live Jobs Page →
        </a>
      </div>
    </div>
    """

    # Wysylka przez Gmail SMTP
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    GMAIL_USER = os.environ.get("GMAIL_USER", "")
    GMAIL_PASS = os.environ.get("GMAIL_PASS", "")

    if not GMAIL_USER or not GMAIL_PASS:
        print("  Brak GMAIL_USER lub GMAIL_PASS — pomijam wyslanie raportu")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[RemoteEDI] Daily report — {new_count} new jobs ({today})"
    msg["From"]    = f"RemoteEDI Bot <{GMAIL_USER}>"
    msg["To"]      = REPORT_EMAIL
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASS)
            server.sendmail(GMAIL_USER, REPORT_EMAIL, msg.as_string())
        print(f"  Raport wyslany na {REPORT_EMAIL}")
    except Exception as e:
        print(f"  Blad wysylki: {e}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("RemoteEDI.com — Raport monitoringu")
    print(f"Start: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    # Wczytaj joby i seen
    jobs     = load_csv(CSV_FILE)
    seen_ids = load_seen()

    print(f"Zaladowano {len(jobs)} jobow z CSV")
    print(f"Poprzednio widzianych: {len(seen_ids)} jobów")

    # Znajdz nowe
    new_jobs = find_new_jobs(jobs, seen_ids)
    print(f"Nowych dzisiaj: {len(new_jobs)}")

    # Zaktualizuj seen
    all_ids = seen_ids | {job_id(j) for j in jobs}
    save_seen(all_ids)
    print(f"Zapisano seen_jobs.json ({len(all_ids)} unikalnych ID)")

    # Wyslij raport
    print("\nWysylam raport...")
    send_report(
        total    = len(jobs),
        new_jobs = new_jobs,
        errors   = []
    )

    print("\nGotowe!")


if __name__ == "__main__":
    main()
