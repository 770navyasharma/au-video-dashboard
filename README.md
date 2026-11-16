# AU Video Watch Dashboard

Daily GA4 + Pinot CDP sync → Google Sheet → static dashboard on GitHub Pages.

## Structure
```
au-video-dashboard/
├── requirements.txt          # Python deps
├── config.py                 # GA property ID, Pinot host, field names
├── fetch_ga.py               # Pulls GA4 data per day → GA_Daily tab
├── fetch_pinot.py            # Pulls Pinot clean-slice data per day → CDP_Daily tab
├── .github/workflows/daily.yml  # Runs 6 AM IST daily; supports manual backfill
├── docs/index.html           # The dashboard (GitHub Pages serves this)
└── README.md
```

## Daily behaviour
- Runs at 6:00 AM IST
- Fetches **last 2 complete days** (today-2 and today-3) — safe lag for GA to finalize
- Idempotent upsert: deletes those dates from sheet, re-inserts fresh
- Sampling check: FAILS the workflow if GA returns sampled data (Navya's rule)

## Backfill
Actions tab → "Daily video data sync" → "Run workflow" → paste comma-separated dates in `backfill_dates` → Run.
