# Landing Page Agency — Build Brief

This repo is a small agency operation that finds local service businesses
running paid ads, cold-emails them, and sells them a $750 conversion-focused
landing page built from a reusable template.

You (Claude Code) are building three things in this repo:

1. A prospect scraper that produces a CSV of qualified leads.
2. A reusable landing page template that can be cloned per client.
3. A 3-email cold outreach sequence with a small script that personalizes and
   queues drafts.

Build them in that order. Confirm each one works before moving to the next.

---

## Operating context

- **Operator:** solo founder, sending from warmed Google Workspace inboxes
  (not main Gmail).
- **Niche:** US local service businesses currently running Google or Meta
  ads. Priority verticals: med spas, dental practices, personal-injury and
  family law firms, HVAC, roofing, solar, chiropractors.
- **Offer:** "Conversion Page Sprint" — $750 flat, 5 business days, includes
  one landing page, one revision round, conversion tracking setup (Plausible
  or PostHog), and a 14-day performance review.
- **Pitch angle:** their ads point at a homepage or generic template page; a
  dedicated landing page typically lifts conversion 2–3x. Sell the outcome,
  not the deliverable.
- **Volume target:** 50+ sends/day across 3 inboxes (15–20 each), Tue–Thu,
  8–10am local to prospect.
- **Brand voice:** direct, confident, outcome-focused, professional but
  approachable. No vague claims, no enterprise jargon, no hype.

---

## Part 1 — Prospect scraper

### Goal

Produce `prospects.csv` with at least 100 qualified leads per run. A lead is
qualified only if the business is **currently running paid ads**.

### Required columns

`business_name, vertical, city, state, website, owner_first_name, email,
ad_platform, ad_evidence_url, notes, scraped_at`

### Sources, in order of preference

1. **Meta Ad Library** (`https://www.facebook.com/ads/library/`) — every
   advertiser is by definition running paid traffic. Filter by country=US, ad
   category=all, and the vertical keyword. This is the primary source.
2. **Google Ads Transparency Center** (`https://adstransparency.google.com/`)
   — same logic for Google advertisers.
3. **Google Maps / Places API** as a fallback to enrich business details
   (address, website, phone) once you have a name.

### Implementation notes

- Use Python. Stack: `requests`, `httpx`, `beautifulsoup4`, `playwright`
  (only if a source requires JS rendering), `pandas` for the CSV.
- Meta Ad Library has no public API — use Playwright to scrape the public
  search UI. Throttle to 1 request every 3–5 seconds. Set a realistic
  user-agent. If you hit a captcha, log it and move to the next vertical/city
  rather than retrying aggressively.
- For email discovery, in this order: (a) check the website's `/contact`,
  `/about`, and footer for a mailto; (b) parse for `firstname@domain`
  patterns; (c) if nothing, leave `email` blank and put a note. **Do not
  guess emails or use permutation tools** — sending to guessed addresses
  tanks domain reputation.
- Owner first name: pull from About / Team / "Meet Dr. X" pages. Leave blank
  if not confidently found. **Never fabricate a name.**
- Deduplicate by domain.

### CLI

```
python scraper/run.py --vertical med_spa --cities "Austin,Dallas,Houston" --limit 150 --out prospects.csv
```

### Acceptance

- Run produces a CSV with ≥100 rows where `ad_evidence_url` is populated.
- No row has a guessed email. Empty is fine; fake is not.
- Re-running with the same args dedupes against existing `prospects.csv`
  rather than overwriting.

---

## Part 2 — Landing page template

### Goal

A single Astro + Tailwind template that can be cloned per client and
customized in under 90 minutes. First page (the template itself) should be
production-grade.

### Stack

- **Framework:** Astro (static, fast, zero JS by default).
- **Styling:** Tailwind CSS.
- **Analytics:** Plausible (script tag, swap domain per client).
- **Forms:** Web3Forms or Formspree (no backend needed; swap key per client).
- **Hosting:** Netlify or Vercel (both free tier).

Read `/mnt/skills/public/frontend-design/SKILL.md` before writing any
component code — it covers the design tokens and patterns expected here.

### Structure

```
template/
  src/
    pages/index.astro          # the landing page
    components/
      Hero.astro
      SocialProof.astro        # logos or "as seen in" strip
      Problem.astro            # the pain the business solves
      Offer.astro              # what they get + pricing if applicable
      Testimonials.astro
      FAQ.astro
      CTA.astro                # repeated 2–3x down the page
      LeadForm.astro
    config/client.ts           # ALL client-specific content lives here
    styles/tokens.css          # color, font, radius tokens
  public/
    images/                    # client images go here
  astro.config.mjs
  tailwind.config.mjs
  README.md                    # per-client setup checklist
```

### Hard rules for the template

- **Single source of truth for client content:** every headline, subhead,
  button label, color, font, phone number, image path, form key, and
  analytics domain lives in `src/config/client.ts`. Components import from
  there. Cloning a new client = edit one file + drop images in
  `/public/images/`.
- **Conversion fundamentals built in:** above-the-fold CTA, sticky mobile
  CTA, 3+ CTAs total down the page, social proof in the first viewport,
  single-field lead form (just phone or email, not both), trust markers
  (license #, years in business, reviews count) near every CTA.
- **Mobile-first.** Test at 375px width.
- **Lighthouse score target: 95+ on performance, accessibility, best
  practices, SEO.** Lazy-load images, use Astro's `<Image>` component, no
  client-side JS unless absolutely required.
- **No stock-photo cliches.** Comment in `client.ts` reminds the operator to
  use real photos of the business/staff.
- **Conversion tracking:** Plausible script in the layout, custom event on
  form submit (`form_submit`), custom event on phone click (`phone_click`).

### Acceptance

- `npm run dev` shows a working page styled with placeholder content from
  `client.ts`.
- Editing only `src/config/client.ts` changes all visible copy and the
  primary brand color.
- `npm run build` produces a static site under 100KB JS total.
- Lighthouse mobile score ≥95 across all four categories.

---

## Part 3 — Cold email sequence + send queue

### Goal

A 3-email sequence with a Python script that takes `prospects.csv`,
personalizes each email, and creates Gmail drafts via the Gmail API (does
**not** send — operator reviews and sends manually).

### Sequence

**Email 1 — Day 0 — Pain hook**

- Subject: `quick note on your {{vertical}} ads`
- Body opens with one specific observation about their current ad → landing
  page setup (e.g., "Saw your Meta ad for [service] is sending traffic to
  your homepage").
- One sentence on why that's likely costing them conversions.
- CTA: offer a free 90-second Loom breakdown of their current page. No pitch
  yet.
- Length: under 75 words.

**Email 2 — Day 3 — Proof + offer**

- Subject: `re: {{vertical}} ads` (threaded reply to Email 1)
- Reference the Loom offer, then make the pitch: $750, 5 days, one revision,
  tracking, 14-day review.
- One concrete proof point (case study line or specific result).
- CTA: 15-min call link or simple yes/no reply.
- Length: under 100 words.

**Email 3 — Day 7 — Breakup**

- Subject: `closing the loop`
- One short paragraph: assuming not a fit, closing their file, here's the
  link if it's ever useful.
- No questions, no asks. Pure permission-to-leave energy.
- Length: under 50 words.

### Personalization tokens

`{{owner_first_name}}` (fall back to "there" if blank), `{{business_name}}`,
`{{vertical}}` (humanized: "med_spa" → "med spa"), `{{city}}`,
`{{ad_platform}}`, `{{ad_evidence_url}}`.

### Script

```
python outreach/queue_drafts.py --csv prospects.csv --inbox anthony@domain.co --sequence 1 --limit 20
```

- `--sequence` selects which email (1, 2, or 3).
- `--limit` caps how many drafts get created in one run (default 20).
- For sequence 2 and 3, the script must look up the original thread by
  subject line and reply within it (so it threads correctly in Gmail).
- Skips any prospect missing an email address.
- Logs each draft created to `outreach/sent_log.csv` with `prospect_email,
  sequence, draft_id, queued_at` so you don't double-queue.

### Hard rules

- **Drafts only, never sends.** Operator reviews every draft before sending.
- **Per-inbox daily cap of 20.** Script refuses to exceed it for a given
  inbox/day.
- **No tracking pixels, no link shorteners.** Both kill deliverability for
  cold mail.
- **Plain text only.** No HTML, no images, no signature graphics. A plain
  text signature with name + one link is fine.

### Acceptance

- Running sequence 1 against a 5-row test CSV produces 5 Gmail drafts in the
  specified inbox, each correctly personalized, each under the word count.
- Running sequence 2 against the same prospects creates threaded replies to
  the original drafts.
- Re-running the same sequence on the same prospects creates zero new
  drafts (dedupe via `sent_log.csv`).

---

## Repo layout

```
/
  scraper/
    run.py
    sources/
      meta_ad_library.py
      google_ads_transparency.py
      enrich_places.py
    requirements.txt
  template/
    (Astro project as specified above)
  outreach/
    queue_drafts.py
    templates/
      email_1.txt
      email_2.txt
      email_3.txt
    sent_log.csv
  prospects.csv          # generated, gitignored
  .env.example           # GMAIL_CREDENTIALS_PATH, PLACES_API_KEY, etc.
  README.md              # operator-facing quickstart
  CLAUDE.md              # this file
```

---

## Build order and checkpoints

1. Scaffold the repo and write `README.md` with operator quickstart.
2. Build the scraper. Stop. Run it against med spas in 3 cities. Show me the
   CSV.
3. Build the landing page template. Stop. Run `npm run dev` and show me a
   screenshot at desktop and mobile widths. Run Lighthouse and show the
   score.
4. Build the outreach script. Stop. Run sequence 1 against a 3-row test CSV.
   Show the drafts created.

After each checkpoint, wait for explicit confirmation before continuing.

---

## What not to build

- No CRM, no dashboard, no admin UI. CSVs and Gmail are the system.
- No automated sending. Drafts only.
- No A/B testing infrastructure for the template. Per-client variations live
  in branches.
- No multi-tenant anything. Each client gets a clone of the template repo.
- No AI-generated stock images on landing pages. Real photos only.
