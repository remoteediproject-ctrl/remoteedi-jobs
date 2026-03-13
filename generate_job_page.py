#!/usr/bin/env python3
"""
RemoteEDI.com — Job Page Generator
Usage: py generate_job_page.py job_data.json
Generates: jobs/[slug].html
"""

import json
import sys
import os
import re
from datetime import datetime, timedelta

def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text

def format_description(text):
    """Convert plain text with newlines to HTML paragraphs and lists."""
    lines = text.strip().split('\n')
    html = []
    in_list = False

    for line in lines:
        line = line.strip()
        if not line:
            if in_list:
                html.append('</ul>')
                in_list = False
            continue

        # Detect bullet points
        if line.startswith(('- ', '• ', '* ', '· ')):
            if not in_list:
                html.append('<ul>')
                in_list = True
            html.append(f'<li>{line[2:].strip()}</li>')
        elif line.endswith(':') and len(line) < 80:
            if in_list:
                html.append('</ul>')
                in_list = False
            html.append(f'<h4>{line}</h4>')
        else:
            if in_list:
                html.append('</ul>')
                in_list = False
            html.append(f'<p>{line}</p>')

    if in_list:
        html.append('</ul>')

    return '\n'.join(html)

def get_formspree_id(job_id):
    """
    Each job gets its own Formspree form so applications go to the right place.
    You need to create a new Formspree form for each job and paste the ID here,
    OR use a single catch-all form and include job_id as a hidden field.
    For MVP: use one catch-all form, job title in subject line identifies the role.
    """
    return "mdawzlya"  # catch-all — zamień na dedykowany ID dla każdego joba jeśli chcesz

def generate(data):
    title    = data['title']
    company  = data['company']
    location = data.get('location', 'Remote')
    salary   = data.get('salary', '')
    job_type = data.get('type', 'Full-time')
    spec     = data.get('specialization', 'EDI General')
    desc     = data['description']
    email    = data.get('contact_email', 'hire@remoteedi.com')
    job_id   = data.get('id', slugify(f"{title}-{company}"))
    posted   = data.get('posted', datetime.now().strftime('%Y-%m-%d'))
    expires  = data.get('expires', (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d'))
    has_ats  = bool(data.get('apply_url', '').strip())
    apply_url = data.get('apply_url', '').strip()

    slug     = slugify(f"{title}-{company}")
    formspree_id = get_formspree_id(job_id)

    # Format posted date nicely
    try:
        posted_dt = datetime.strptime(posted, '%Y-%m-%d')
        posted_display = posted_dt.strftime('%B %d, %Y')
    except:
        posted_display = posted

    desc_html = format_description(desc)

    # Apply section — ATS link or inline form
    if has_ats:
        apply_section = f"""
        <div class="apply-box">
          <p class="apply-note">Applications are handled externally. You'll be taken to the employer's application page.</p>
          <a href="{apply_url}" target="_blank" rel="noopener" class="btn-apply">Apply for this role →</a>
          <p class="apply-sub">Opens in a new tab</p>
        </div>
"""
    else:
        apply_section = f"""
        <div class="apply-box">
          <h3 class="apply-title">Apply for this role</h3>
          <p class="apply-note">Send your application directly. The employer will contact you by email.</p>
          <form id="applyForm" novalidate>
            <div class="field-group" id="fg-name">
              <label for="applicant_name">Full name <span class="req">*</span></label>
              <input type="text" id="applicant_name" name="applicant_name" placeholder="Jane Smith" autocomplete="name">
              <div class="field-err">Required.</div>
            </div>
            <div class="field-group" id="fg-email">
              <label for="applicant_email">Email <span class="req">*</span></label>
              <input type="email" id="applicant_email" name="applicant_email" placeholder="jane@email.com" autocomplete="email">
              <div class="field-err">Please enter a valid email.</div>
            </div>
            <div class="field-group">
              <label for="linkedin">LinkedIn profile <span class="opt">(optional)</span></label>
              <input type="url" id="linkedin" name="linkedin" placeholder="https://linkedin.com/in/...">
            </div>
            <div class="field-group" id="fg-cover">
              <label for="cover">Why are you a good fit? <span class="req">*</span></label>
              <textarea id="cover" name="cover" rows="5" placeholder="Brief intro — your EDI experience, relevant tools, what interests you about this role..."></textarea>
              <div class="field-err">Please add a short intro (min. 50 characters).</div>
            </div>
            <div class="field-group">
              <label for="resume_url">CV / Resume link <span class="opt">(optional)</span></label>
              <input type="url" id="resume_url" name="resume_url" placeholder="Google Drive, Dropbox, or LinkedIn URL">
              <div class="input-hint">No file upload — paste a link to your CV.</div>
            </div>

            <!-- Hidden fields for context -->
            <input type="hidden" name="_subject" value="Application: {title} at {company} [RemoteEDI.com]">
            <input type="hidden" name="job_title" value="{title}">
            <input type="hidden" name="company" value="{company}">
            <input type="hidden" name="job_id" value="{job_id}">
            <input type="hidden" name="_replyto" id="_replyto">

            <button type="submit" class="btn-apply" id="submitBtn">Send Application →</button>
            <div id="applySuccess" class="apply-success" style="display:none">
              ✓ Application sent! The employer will be in touch if your profile is a match.
            </div>
          </form>
        </div>
"""

    apply_js = "" if has_ats else f"""
  // Application form
  const form = document.getElementById('applyForm');
  if (form) {{
    document.getElementById('_replyto').value = document.getElementById('applicant_email')?.value || '';

    function validateApp() {{
      let ok = true;
      const checks = [
        {{ id: 'applicant_name',  fg: 'fg-name',  fn: v => v.trim().length > 1 }},
        {{ id: 'applicant_email', fg: 'fg-email', fn: v => v.includes('@') && v.includes('.') }},
        {{ id: 'cover',           fg: 'fg-cover', fn: v => v.trim().length >= 50 }},
      ];
      let first = null;
      checks.forEach(c => {{
        const el = document.getElementById(c.id);
        const fg = document.getElementById(c.fg);
        const pass = c.fn(el.value);
        fg.classList.toggle('has-error', !pass);
        if (!pass && !first) first = el;
        if (!pass) ok = false;
      }});
      if (first) first.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
      return ok;
    }}

    ['applicant_name','applicant_email','cover'].forEach(id => {{
      const el = document.getElementById(id);
      el.addEventListener('blur', function() {{ this.dataset.touched='1'; validateApp(); }});
      el.addEventListener('input', function() {{ if(this.dataset.touched) validateApp(); }});
    }});

    form.addEventListener('submit', async function(e) {{
      e.preventDefault();
      if (!validateApp()) return;

      // Sync reply-to with email field
      document.getElementById('_replyto').value = document.getElementById('applicant_email').value;

      const btn = document.getElementById('submitBtn');
      btn.disabled = true;
      btn.textContent = 'Sending...';

      const payload = {{
        applicant_name:  document.getElementById('applicant_name').value.trim(),
        applicant_email: document.getElementById('applicant_email').value.trim(),
        linkedin:        document.getElementById('linkedin').value.trim(),
        cover:           document.getElementById('cover').value.trim(),
        resume_url:      document.getElementById('resume_url').value.trim(),
        job_title:       '{title}',
        company:         '{company}',
        job_id:          '{job_id}',
        _subject:        'Application: {title} at {company} [RemoteEDI.com]',
      }};

      try {{
        const res = await fetch('https://formspree.io/f/{formspree_id}', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json', 'Accept': 'application/json' }},
          body: JSON.stringify(payload)
        }});
        if (!res.ok) throw new Error();
      }} catch(err) {{
        btn.disabled = false;
        btn.textContent = 'Send Application →';
        alert('Something went wrong. Please try again or email hire@remoteedi.com');
        return;
      }}

      form.style.display = 'none';
      document.getElementById('applySuccess').style.display = 'block';
    }});
  }}
"""

    salary_html = f'<div class="meta-item"><span class="meta-label">Salary</span><span class="meta-val">{salary}</span></div>' if salary else ''
    spec_slug = slugify(spec)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} at {company} — RemoteEDI.com</title>
  <meta name="description" content="{job_type} remote EDI role at {company}. {location}. Apply on RemoteEDI.com.">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=DM+Sans:ital,wght@0,400;0,500;0,600;1,400&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{
      --bg:      #0b0f0e;
      --bg2:     #111614;
      --bg3:     #181e1c;
      --accent:  #00e5a0;
      --accent2: #00b87a;
      --text:    #e8ede9;
      --muted:   #7a8c82;
      --border:  #1e2926;
      --error:   #e17055;
      --radius:  10px;
    }}
    html {{ scroll-behavior: smooth; }}
    body {{ background: var(--bg); color: var(--text); font-family: 'DM Sans', sans-serif; min-height: 100vh; }}

    /* NAV */
    nav {{
      position: fixed; top: 0; left: 0; right: 0; z-index: 100;
      height: 58px; display: flex; align-items: center; justify-content: space-between;
      padding: 0 2rem; background: rgba(11,15,14,0.92); backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--border);
    }}
    .logo {{ font-family: 'IBM Plex Mono', monospace; font-size: 0.95rem; color: var(--accent); text-decoration: none; font-weight: 600; }}
    .nav-right {{ display: flex; align-items: center; gap: 0.5rem; }}
    .nav-right a {{ color: var(--muted); text-decoration: none; font-size: 0.85rem; padding: 0.4rem 0.8rem; border-radius: 6px; transition: color 0.2s; }}
    .nav-right a:hover {{ color: var(--text); }}
    .nav-right .nav-post {{ background: var(--accent); color: #000; font-family: 'IBM Plex Mono', monospace; font-size: 0.8rem; font-weight: 600; }}
    .nav-right .nav-post:hover {{ background: var(--accent2); color: #000; }}

    /* BREADCRUMB */
    .breadcrumb {{
      max-width: 1000px; margin: 0 auto; padding: 5rem 2rem 0;
      font-size: 0.78rem; color: var(--muted); display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap;
    }}
    .breadcrumb a {{ color: var(--muted); text-decoration: none; }}
    .breadcrumb a:hover {{ color: var(--accent); }}
    .breadcrumb span {{ color: var(--border); }}

    /* LAYOUT */
    .page {{ max-width: 1000px; margin: 0 auto; padding: 1.5rem 2rem 5rem; display: grid; grid-template-columns: 1fr 320px; gap: 3rem; align-items: start; }}

    /* JOB HEADER */
    .job-header {{ margin-bottom: 2rem; padding-bottom: 2rem; border-bottom: 1px solid var(--border); }}
    .job-spec-tag {{
      display: inline-block; font-family: 'IBM Plex Mono', monospace; font-size: 0.7rem;
      font-weight: 600; color: var(--accent); background: rgba(0,229,160,0.08);
      border: 1px solid rgba(0,229,160,0.2); padding: 0.3rem 0.7rem; border-radius: 4px;
      text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 1rem;
    }}
    .job-title {{ font-size: clamp(1.4rem, 3vw, 2rem); font-weight: 700; line-height: 1.2; margin-bottom: 0.5rem; }}
    .job-company {{ font-size: 1rem; color: var(--muted); margin-bottom: 1.25rem; }}
    .job-company strong {{ color: var(--text); }}

    .meta-row {{ display: flex; flex-wrap: wrap; gap: 0.75rem; }}
    .meta-item {{
      background: var(--bg2); border: 1px solid var(--border); border-radius: 6px;
      padding: 0.4rem 0.75rem; display: flex; flex-direction: column; gap: 0.1rem;
    }}
    .meta-label {{ font-family: 'IBM Plex Mono', monospace; font-size: 0.6rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; }}
    .meta-val {{ font-size: 0.82rem; font-weight: 500; color: var(--text); }}

    /* JOB DESCRIPTION */
    .job-description {{ line-height: 1.75; color: var(--text); }}
    .job-description h4 {{ font-size: 0.92rem; font-weight: 600; color: var(--text); margin: 1.5rem 0 0.5rem; font-family: 'IBM Plex Mono', monospace; text-transform: uppercase; letter-spacing: 0.05em; font-size: 0.75rem; color: var(--muted); }}
    .job-description p {{ font-size: 0.92rem; color: var(--muted); margin-bottom: 0.75rem; line-height: 1.75; }}
    .job-description ul {{ margin: 0.5rem 0 1rem 1.25rem; }}
    .job-description li {{ font-size: 0.9rem; color: var(--muted); margin-bottom: 0.35rem; line-height: 1.6; }}

    /* SIDEBAR */
    .sidebar {{ position: sticky; top: 80px; display: flex; flex-direction: column; gap: 1rem; }}

    /* APPLY BOX */
    .apply-box {{
      background: var(--bg2); border: 1px solid var(--border); border-radius: var(--radius); padding: 1.5rem;
    }}
    .apply-title {{ font-size: 0.92rem; font-weight: 600; margin-bottom: 0.5rem; }}
    .apply-note {{ font-size: 0.8rem; color: var(--muted); line-height: 1.6; margin-bottom: 1.25rem; }}
    .apply-sub {{ font-size: 0.72rem; color: var(--muted); text-align: center; margin-top: 0.5rem; }}
    .apply-success {{ font-size: 0.85rem; color: var(--accent); font-family: 'IBM Plex Mono', monospace; padding: 1rem 0; line-height: 1.6; }}

    .btn-apply {{
      display: block; width: 100%; background: var(--accent); color: #000; border: none;
      font-family: 'IBM Plex Mono', monospace; font-weight: 600; font-size: 0.88rem;
      padding: 0.85rem 1rem; border-radius: var(--radius); text-align: center;
      text-decoration: none; cursor: pointer; transition: background 0.2s;
    }}
    .btn-apply:hover {{ background: var(--accent2); }}
    .btn-apply:disabled {{ background: var(--border); color: var(--muted); cursor: not-allowed; }}

    /* FORM */
    .field-group {{ margin-bottom: 1rem; }}
    label {{ display: block; font-family: 'IBM Plex Mono', monospace; font-size: 0.68rem; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 0.4rem; }}
    .req {{ color: var(--accent); }}
    .opt {{ color: var(--border); font-weight: 400; text-transform: none; letter-spacing: 0; }}
    input[type="text"], input[type="email"], input[type="url"], textarea {{
      width: 100%; background: var(--bg3); border: 1px solid var(--border); border-radius: 8px;
      padding: 0.65rem 0.85rem; color: var(--text); font-family: 'DM Sans', sans-serif;
      font-size: 0.88rem; outline: none; transition: border-color 0.2s;
    }}
    input:focus, textarea:focus {{ border-color: var(--accent); }}
    input::placeholder, textarea::placeholder {{ color: var(--border); }}
    textarea {{ resize: vertical; line-height: 1.6; }}
    .input-hint {{ font-size: 0.72rem; color: var(--muted); margin-top: 0.3rem; }}
    .field-err {{ font-size: 0.72rem; color: var(--error); margin-top: 0.3rem; display: none; }}
    .has-error input, .has-error textarea {{ border-color: var(--error); }}
    .has-error .field-err {{ display: block; }}

    /* COMPANY CARD */
    .company-card {{
      background: var(--bg2); border: 1px solid var(--border); border-radius: var(--radius); padding: 1.25rem;
    }}
    .company-card h4 {{ font-family: 'IBM Plex Mono', monospace; font-size: 0.7rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 0.75rem; }}
    .company-name {{ font-size: 0.92rem; font-weight: 600; margin-bottom: 0.25rem; }}
    .company-meta {{ font-size: 0.78rem; color: var(--muted); line-height: 1.6; }}

    /* SHARE */
    .share-card {{
      background: var(--bg2); border: 1px solid var(--border); border-radius: var(--radius); padding: 1.25rem;
    }}
    .share-card h4 {{ font-family: 'IBM Plex Mono', monospace; font-size: 0.7rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 0.75rem; }}
    .share-url {{
      background: var(--bg3); border: 1px solid var(--border); border-radius: 6px;
      padding: 0.5rem 0.75rem; font-family: 'IBM Plex Mono', monospace; font-size: 0.72rem;
      color: var(--muted); word-break: break-all; cursor: pointer; transition: border-color 0.2s;
    }}
    .share-url:hover {{ border-color: var(--accent); color: var(--accent); }}
    .share-hint {{ font-size: 0.72rem; color: var(--muted); margin-top: 0.4rem; }}

    /* EXPIRED BANNER */
    .expired-banner {{
      background: rgba(225,112,85,0.1); border: 1px solid rgba(225,112,85,0.3);
      border-radius: var(--radius); padding: 1rem 1.25rem; margin-bottom: 1.5rem;
      font-size: 0.85rem; color: #e17055; line-height: 1.5; display: none;
    }}

    /* BACK LINK */
    .back-link {{ margin-bottom: 1.5rem; }}
    .back-link a {{ font-size: 0.82rem; color: var(--muted); text-decoration: none; display: inline-flex; align-items: center; gap: 0.4rem; transition: color 0.2s; }}
    .back-link a:hover {{ color: var(--accent); }}

    @media (max-width: 768px) {{
      .page {{ grid-template-columns: 1fr; padding: 1rem 1rem 4rem; gap: 2rem; }}
      .sidebar {{ position: static; }}
      nav {{ padding: 0 1rem; }}
      .breadcrumb {{ padding: 5rem 1rem 0; }}
    }}
  </style>
</head>
<body>

<nav>
  <a href="/" class="logo">RemoteEDI.com</a>
  <div class="nav-right">
    <a href="/jobs.html">All Jobs</a>
    <a href="/employers.html" class="nav-post">Post a Job</a>
  </div>
</nav>

<div class="breadcrumb">
  <a href="/">Home</a>
  <span>/</span>
  <a href="/jobs.html">Jobs</a>
  <span>/</span>
  <span>{title}</span>
</div>

<div class="page">

  <!-- MAIN CONTENT -->
  <div class="main-col">

    <div class="back-link">
      <a href="/jobs.html">← Back to all jobs</a>
    </div>

    <div id="expiredBanner" class="expired-banner">
      This position may no longer be accepting applications — it was listed over 30 days ago.
    </div>

    <div class="job-header">
      <div class="job-spec-tag">{spec}</div>
      <h1 class="job-title">{title}</h1>
      <p class="job-company">at <strong>{company}</strong></p>
      <div class="meta-row">
        <div class="meta-item">
          <span class="meta-label">Location</span>
          <span class="meta-val">{location}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">Type</span>
          <span class="meta-val">{job_type}</span>
        </div>
        {salary_html}
        <div class="meta-item">
          <span class="meta-label">Posted</span>
          <span class="meta-val">{posted_display}</span>
        </div>
      </div>
    </div>

    <div class="job-description">
      {desc_html}
    </div>

  </div>

  <!-- SIDEBAR -->
  <div class="sidebar">

    {apply_section}

    <div class="company-card">
      <h4>About the employer</h4>
      <div class="company-name">{company}</div>
      <div class="company-meta">{location} &nbsp;·&nbsp; {job_type}</div>
    </div>

    <div class="share-card">
      <h4>Share this job</h4>
      <div class="share-url" onclick="copyUrl()" title="Click to copy">
        remoteedi.com/jobs/{slug}.html
      </div>
      <div class="share-hint" id="copyHint">Click to copy link</div>
    </div>

  </div>
</div>

<script>
  // Check if job is expired
  const expires = new Date('{expires}');
  if (new Date() > expires) {{
    document.getElementById('expiredBanner').style.display = 'block';
  }}

  // Copy URL
  function copyUrl() {{
    const url = window.location.href;
    navigator.clipboard.writeText(url).then(function() {{
      document.getElementById('copyHint').textContent = '✓ Copied!';
      setTimeout(function() {{
        document.getElementById('copyHint').textContent = 'Click to copy link';
      }}, 2000);
    }});
  }}

  {apply_js}
</script>

</body>
</html>"""

    return slug, html


def main():
    if len(sys.argv) < 2:
        print("Usage: py generate_job_page.py job_data.json")
        print("\nExample job_data.json:")
        example = {
            "id": "edi-analyst-acme-2026",
            "title": "Senior EDI Analyst",
            "company": "Acme Corp",
            "location": "Remote USA",
            "salary": "$90,000 – $120,000/yr",
            "type": "Full-time",
            "specialization": "Healthcare EDI",
            "apply_url": "",
            "contact_email": "recruiter@acme.com",
            "posted": datetime.now().strftime('%Y-%m-%d'),
            "description": "We are looking for a Senior EDI Analyst to join our team.\n\nResponsibilities:\n- Develop and maintain EDI mappings\n- Onboard new trading partners\n- Troubleshoot X12 transactions\n\nRequirements:\n- 3+ years EDI experience\n- Experience with 837/835 healthcare transactions\n- Knowledge of AS2 and SFTP protocols"
        }
        print(json.dumps(example, indent=2))
        sys.exit(1)

    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        data = json.load(f)

    slug, html = generate(data)

    os.makedirs('jobs', exist_ok=True)
    out_path = os.path.join('jobs', f'{slug}.html')

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"✓ Generated: {out_path}")
    print(f"  URL: remoteedi.com/jobs/{slug}.html")
    print(f"  Title: {data['title']} at {data['company']}")


if __name__ == '__main__':
    main()
