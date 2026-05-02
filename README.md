# Landing Page Agency — Operator Quickstart

Three-part toolkit for a one-person agency that finds local service businesses
running paid ads, cold-emails them, and sells them a $750 conversion-focused
landing page.

The full build brief and product rules live in [CLAUDE.md](./CLAUDE.md). This
file is the day-to-day operator manual.

---

## Offer

**Conversion Page Sprint** — $750 flat, 5 business days. Includes one landing
page, one revision round, conversion tracking setup (Plausible or PostHog), and
a 14-day performance review.

Pitch the outcome: their ads point at a homepage; a dedicated landing page
typically lifts conversion 2–3x.

---

## Daily routine (what to actually do)

```
Mon          scrape new leads, review CSV, queue email 1 drafts (Tue send)
Tue 8–10am   review drafts, hit send across all 3 inboxes
Wed 8–10am   send any holdovers
Thu          queue email 2 follow-ups for last week's batch
Fri          replies / Loom recordings / new client kickoff
```

Volume target: 50+ sends/day across 3 warmed inboxes (15–20 each), Tue–Thu,
8–10am local-to-prospect.

---

## Setup (one time)

### 1. Clone and install

```bash
git clone <this-repo>
cd <this-repo>
cp .env.example .env   # fill in keys as you wire each piece
```

### 2. Python deps (scraper + outreach)

```bash
python -m venv .venv
source .venv/bin/activate

pip install -r scraper/requirements.txt
pip install -r outreach/requirements.txt

# Playwright browser binaries (scraper)
python -m playwright install chromium
```

### 3. Gmail API (outreach)

1. Create a Google Cloud project, enable the Gmail API.
2. Configure an OAuth consent screen (External, Testing is fine for solo use).
3. Create OAuth credentials → Desktop app → download the JSON.
4. Save it to `gmail_credentials.json` at the repo root (path is configurable
   via `GMAIL_CREDENTIALS_PATH` in `.env`).
5. Add each sending inbox as a Test User on the consent screen.

First run of `outreach/queue_drafts.py` will open a browser for each inbox
once and cache the token under `.gmail_tokens/`.

### 4. Landing page template

```bash
cd template
npm install
npm run dev
```

Per-client setup checklist lives in `template/README.md`.

---

## Part 1 — Scraper

Pulls advertisers from Meta Ad Library and Google Ads Transparency Center,
enriches with Google Places, writes `prospects.csv`.

```bash
python scraper/run.py \
  --vertical med_spa \
  --cities "Austin,Dallas,Houston" \
  --limit 150 \
  --out prospects.csv
```

- Re-running the same args **dedupes against existing `prospects.csv`** rather
  than overwriting.
- A row is only included if `ad_evidence_url` is populated (proof they're
  currently advertising).
- Empty `email` is fine. Guessed email is not — never guess.

Supported verticals: `med_spa`, `dental`, `personal_injury_law`,
`family_law`, `hvac`, `roofing`, `solar`, `chiropractor`.

---

## Part 2 — Landing page template

Astro + Tailwind. Single source of truth for client content lives in
`template/src/config/client.ts`. Cloning a new client = edit that one file +
drop images in `template/public/images/`.

```bash
cd template
npm run dev      # local preview at http://localhost:4321
npm run build    # static build to dist/
npm run preview  # serve the production build
```

Lighthouse target: ≥95 mobile across performance, accessibility, best
practices, SEO.

Per-client setup is documented in `template/README.md`.

---

## Part 3 — Outreach

3-email cold sequence. Script creates Gmail **drafts** — never sends. You
review every draft before hitting send.

```bash
# Day 0: pain hook
python outreach/queue_drafts.py --csv prospects.csv \
  --inbox anthony@domain.co --sequence 1 --limit 20

# Day 3: proof + offer (threaded reply to email 1)
python outreach/queue_drafts.py --csv prospects.csv \
  --inbox anthony@domain.co --sequence 2 --limit 20

# Day 7: breakup
python outreach/queue_drafts.py --csv prospects.csv \
  --inbox anthony@domain.co --sequence 3 --limit 20
```

- Hard cap of **20 drafts per inbox per day** — script refuses to exceed it.
- Logs every draft to `outreach/sent_log.csv`. Re-running the same sequence on
  the same prospects creates **zero** new drafts.
- Skips any prospect with a blank `email`.
- No tracking pixels. No link shorteners. Plain text only.

---

## Sending hygiene (read this once, then live by it)

- Send from warmed Workspace inboxes — never your main Gmail.
- Stay under 20 sends per inbox per day for the first 30 days.
- Tue/Wed/Thu only, between 8–10am local-to-prospect.
- If you get more than 1 spam complaint per 100 sends, pause that inbox and
  re-warm it.
- One link per email max. No images, no signatures with logos.
- If a prospect replies "remove" / "unsubscribe" / negative — log the domain
  in `outreach/suppressions.txt` and never email them again.

---

## File layout

```
/
├── scraper/
│   ├── run.py                       # CLI entrypoint
│   ├── sources/
│   │   ├── meta_ad_library.py       # Playwright scraper
│   │   ├── google_ads_transparency.py
│   │   └── enrich_places.py         # Places API enrichment
│   └── requirements.txt
├── template/                        # Astro landing page template
├── outreach/
│   ├── queue_drafts.py              # creates Gmail drafts
│   ├── templates/
│   │   ├── email_1.txt
│   │   ├── email_2.txt
│   │   └── email_3.txt
│   ├── sent_log.csv                 # generated, gitignored
│   └── requirements.txt
├── prospects.csv                    # generated, gitignored
├── .env.example
├── README.md                        # this file
└── CLAUDE.md                        # full build brief / product spec
```

---

## What this repo deliberately does NOT have

- No CRM. No dashboard. No admin UI. CSVs and Gmail are the system.
- No automated sending. Drafts only.
- No A/B testing infra in the template — variations live in branches.
- No multi-tenant anything — each client gets a clone of `template/`.
- No AI-generated stock images on landing pages. Real photos only.
