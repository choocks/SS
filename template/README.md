# Conversion Page Sprint — Landing Page Template

Astro + Tailwind. Single source of truth for client content lives in
[`src/config/client.ts`](./src/config/client.ts). Cloning a new client = edit
that one file and drop real photos into `/public/images/`.

---

## Per-client setup checklist (target: under 90 minutes)

1. **Clone the template repo** to a new repo for this client.
2. **Open `src/config/client.ts`** and replace every value top-to-bottom:
   - `brand.name` and `meta.*` (domain, title, description)
   - `brand.primaryColor` / `primaryColorDark` (use the client's actual brand
     colors — not a vibes-based teal)
   - `contact.*` (phone displays + tel link, email, address, hours)
   - `hero.*`, `trustMarkers`, `socialProof.*`, `problem.*`, `offer.*`
   - `testimonials.items` — pull verbatim from real reviews. Never invent
     quotes.
   - `faq.items`, `finalCta.*`
   - `form.web3formsKey` — create at https://web3forms.com (free), one key
     per client. Set `form.fieldType` to `'phone'` or `'email'` (not both).
   - `analytics.plausibleDomain` — match what's set up in Plausible.
3. **Drop real photos** into `/public/images/`. The hero image path is set
   in `client.ts`. Replace `hero.svg` placeholder with a JPG/WebP photo of
   the actual business — staff, treatment room, work-in-progress, finished
   results. **No stock photos. No AI imagery. No headset call-center
   shots.** A blurry real photo converts better than a polished fake one.
4. **Replace the favicon** at `/public/favicon.svg`.
5. **Run locally:** `npm install && npm run dev` → http://localhost:4321
6. **Test at 375px width** (Chrome devtools → iPhone SE). Sticky mobile CTA
   should sit above the fold of the keyboard. Phone tap should fire a tel:
   link. Form should submit to Web3Forms.
7. **Lighthouse:** `npm run build && npm run preview`, then run Lighthouse
   in incognito. Target ≥95 on all four categories. If anything fails,
   it's almost always image weight — re-export hero photo at WebP/AVIF
   under 200KB.
8. **Deploy** to Netlify or Vercel. Both auto-detect Astro and need zero
   config. Point the client's domain at it.
9. **Verify Plausible events fire:** load the page in another browser,
   click the phone link, submit the form. `phone_click` and `form_submit`
   should show up in the Plausible dashboard within 2 minutes.

---

## What's wired up

- **Above-the-fold CTA** — Hero has the lead form right next to the
  headline.
- **Sticky mobile CTA** — `StickyMobileCTA.astro` pins to the bottom on
  small screens.
- **3+ CTAs total** — Hero form, Offer form, final CTA section, plus the
  mobile sticky and the click-to-call in the Footer.
- **Trust markers near every CTA** — `trustMarkers` from `client.ts` render
  under each form.
- **Single-field lead form** — phone OR email, set via `form.fieldType`.
- **Plausible custom events** — zero JS thanks to the
  `script.tagged-events.js` Plausible variant. Class names like
  `plausible-event-name=phone_click` are picked up automatically.
- **Image lazy-loading** — `loading="lazy"` on every image except the hero
  (which uses `fetchpriority="high"`).

---

## Common edits

**Change the brand color:** edit `brand.primaryColor` and
`brand.primaryColorDark` in `client.ts`. Every CTA, eyebrow, link hover,
and the final CTA section background updates automatically. The hero
image background tint and FAQ open-state ring also derive from it.

**Add a new section:** drop a component into `src/components/`, import it
in `src/pages/index.astro`, and add its data to the `ClientConfig`
interface in `client.ts`.

**Tighten the page:** if a client doesn't have testimonials yet, comment
out `<Testimonials />` in `index.astro`. Don't ship fake testimonials.

**Multi-page (privacy / terms / thank-you):** add `.astro` files to
`src/pages/`. Astro auto-routes them.

---

## Hosting

```bash
npm run build      # → dist/
npm run preview    # serves dist/ on http://localhost:4321
```

- **Netlify:** drag-and-drop `dist/` or connect the repo. No build config
  needed.
- **Vercel:** connect the repo, framework preset = Astro, no build config
  needed.

---

## Rules to not break

- **Plain HTML form, no JS.** Web3Forms posts via standard form action.
  Adding a JS form handler will hurt Lighthouse.
- **No tracking pixels in cold-mail context.** This template is fine for
  the landing page itself. Don't paste Meta Pixel / GA4 in the layout —
  Plausible covers what you actually need.
- **Don't fabricate testimonials.** Pull verbatim from real reviews and
  ask permission before publishing names.
- **One brand color per page.** No rainbow gradients, no neon accents.
- **Single-field form.** Don't add a name field, a service-of-interest
  dropdown, or anything else. Every extra field reduces conversion.
