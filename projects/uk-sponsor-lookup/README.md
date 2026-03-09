# UK Sponsor Lookup Tool

**Live URL:** https://uk-sponsored-lookup.onrender.com/

## Overview
Search UK sponsor companies by name or job posting URL (LinkedIn, Indeed, Glassdoor).

## Database Status
✅ **Updated:** March 9, 2026 (140,854 sponsors)
- Previously: Feb 8, 2026 (140,448 sponsors)
- Change: +406 new sponsors

## Features
- Search by company name
- Search by job posting URL
- 140,000+ sponsor records
- External links (LinkedIn, Indeed, Glassdoor, Companies House)
- Match scoring and confidence ratings

## Tech Stack
- Python (Flask)
- SQLite database
- HTML/CSS frontend

## Local Development

```bash
pip install -r requirements.txt
python api.py
```

Then open http://localhost:5000

## Deployment
See DEPLOY.md for Render deployment instructions.

## Updating the Database

The UK Government updates the sponsor list weekly. To update:

```bash
python update_sponsors.py
```

This will:
1. Download the latest CSV from GOV.UK
2. Backup the current data
3. Replace with new data

### Automated Updates
Set up a cron job to run weekly:

```bash
# Weekly on Monday at 6 AM
0 6 * * 1 cd /path/to/uk-sponsor-lookup && python update_sponsors.py >> update.log 2>&1
```

Note: The Render deployment will need to trigger a restart after the CSV updates (or use a volume mount).
