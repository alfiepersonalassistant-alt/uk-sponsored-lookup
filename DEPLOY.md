# UK Sponsor Lookup - Deployment Files

## Files Included

| File | Purpose |
|------|---------|
| `api.py` | Flask API server (updated to serve HTML) |
| `sponsor_lookup.py` | Core search logic |
| `index.html` | Frontend web interface |
| `uk_sponsors.csv` | Sponsor database (140k+ records) |
| `requirements.txt` | Python dependencies |
| `wsgi.py` | Entry point for Render |
| `render.yaml` | Render deployment config |

## Deploy to Render (3 steps)

### Option 1: GitHub + Render (Recommended)

1. **Create a new GitHub repo** (e.g., `uk-sponsor-lookup`)
2. **Upload these files** to the repo
3. **Go to render.com** → Click "New Web Service" → Connect your GitHub repo
4. **Click Deploy** — Render will read `render.yaml` and configure everything

### Option 2: Direct Upload to Render

1. **Go to render.com** → "New Web Service" → "Python"
2. **Upload files** or paste them in
3. **Set start command:** `gunicorn wsgi:app --bind 0.0.0.0:$PORT`
4. **Click Deploy**

## After Deploy

Your app will be live at: `https://uk-sponsor-lookup-[random].onrender.com`

The frontend loads at the root `/` and the API is at `/api/*`

## Local Testing (Optional)

```bash
pip install -r requirements.txt
python api.py
```

Then open http://localhost:5000

---

**Ready to deploy!** 🚀
