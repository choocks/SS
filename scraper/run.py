"""Prospect scraper CLI entrypoint.

Pulls advertisers from Meta Ad Library and Google Ads Transparency Center,
enriches with Google Places, crawls each website for a published email and
owner first name, and appends to prospects.csv (deduping by domain).

Usage:
    python scraper/run.py --vertical med_spa \\
        --cities "Austin,Dallas,Houston" \\
        --limit 150 \\
        --out prospects.csv
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

# Allow running this file directly: `python scraper/run.py …`
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR.parent))

from scraper.lib import (  # noqa: E402
    COLUMNS,
    CITY_STATE,
    Lead,
    VERTICALS,
    domain_of,
    find_contact,
)
from scraper.sources.enrich_places import enrich_with_places  # noqa: E402
from scraper.sources.google_ads_transparency import scrape_google_ads  # noqa: E402
from scraper.sources.meta_ad_library import scrape_meta  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Scrape qualified leads (currently advertising local businesses) into a CSV."
    )
    p.add_argument(
        "--vertical",
        required=True,
        choices=sorted(VERTICALS.keys()),
        help="Business vertical to target.",
    )
    p.add_argument(
        "--cities",
        required=True,
        help='Comma-separated US cities, e.g. "Austin,Dallas,Houston".',
    )
    p.add_argument(
        "--limit",
        type=int,
        default=150,
        help="Max NEW leads per run across all cities (default 150).",
    )
    p.add_argument(
        "--out",
        default="prospects.csv",
        help="Output CSV path. Existing file is appended to (deduped by domain).",
    )
    p.add_argument(
        "--skip-meta", action="store_true", help="Skip Meta Ad Library source."
    )
    p.add_argument(
        "--skip-google",
        action="store_true",
        help="Skip Google Ads Transparency source.",
    )
    p.add_argument(
        "--skip-enrich",
        action="store_true",
        help="Skip Google Places enrichment for leads missing a website.",
    )
    p.add_argument(
        "--skip-contact",
        action="store_true",
        help="Skip per-website email/owner crawl.",
    )
    p.add_argument(
        "--headed",
        action="store_true",
        help="Run Playwright with a visible browser (for debugging).",
    )
    return p.parse_args(argv)


def load_existing(path: Path) -> tuple[list[dict], set[str]]:
    if not path.exists():
        return [], set()
    df = pd.read_csv(path, dtype=str).fillna("")
    rows = df.to_dict("records")
    domains = {domain_of(r.get("website", "")) for r in rows}
    domains.discard("")
    return rows, domains


def dedupe_new(leads: list[Lead], existing_domains: set[str]) -> list[Lead]:
    """Drop leads whose domain we already have, and dedupe within `leads`."""
    out: list[Lead] = []
    seen = set(existing_domains)
    seen_names = set()
    for lead in leads:
        d = domain_of(lead.website)
        if d:
            if d in seen:
                continue
            seen.add(d)
        else:
            key = (lead.business_name.lower(), lead.city.lower())
            if key in seen_names:
                continue
            seen_names.add(key)
        out.append(lead)
    return out


def maybe_enrich(lead: Lead, places_key: str | None) -> None:
    if not places_key or lead.website:
        return
    info = enrich_with_places(lead.business_name, lead.city, lead.state, api_key=places_key)
    if info.get("_error"):
        lead.append_note(f"places error: {info['_error']}")
        return
    if info.get("website"):
        lead.website = info["website"]
    if info.get("phone"):
        lead.append_note(f"phone: {info['phone']}")
    if info.get("address"):
        lead.append_note(f"addr: {info['address']}")


def maybe_find_contact(lead: Lead) -> None:
    if not lead.website:
        lead.append_note("no website; skipped contact crawl")
        return
    email, first_name, note = find_contact(lead.website)
    if email:
        lead.email = email
    if first_name and not lead.owner_first_name:
        lead.owner_first_name = first_name
    if note:
        lead.append_note(note)


async def collect_leads(args: argparse.Namespace) -> list[Lead]:
    cities = [c.strip() for c in args.cities.split(",") if c.strip()]
    if not cities:
        raise SystemExit("--cities was empty")

    per_city = max(1, args.limit // len(cities) + 1)
    leads: list[Lead] = []
    headless = not args.headed

    for city in cities:
        state = CITY_STATE.get(city.lower(), "")
        if len(leads) >= args.limit:
            break

        if not args.skip_meta:
            try:
                meta_leads = await scrape_meta(
                    args.vertical, city, state, per_city, headless=headless
                )
                print(f"[meta] {city}: {len(meta_leads)} leads")
                leads.extend(meta_leads)
            except Exception as e:
                print(f"[meta] {city}: error — {e}")

        if not args.skip_google and len(leads) < args.limit:
            try:
                g_leads = await scrape_google_ads(
                    args.vertical, city, state, per_city, headless=headless
                )
                print(f"[google] {city}: {len(g_leads)} leads")
                leads.extend(g_leads)
            except Exception as e:
                print(f"[google] {city}: error — {e}")

    return leads[: args.limit]


async def amain() -> int:
    load_dotenv()
    args = parse_args()

    out_path = Path(args.out)
    existing_rows, existing_domains = load_existing(out_path)
    print(f"loaded {len(existing_rows)} existing rows ({len(existing_domains)} unique domains)")

    raw = await collect_leads(args)
    print(f"raw leads from sources: {len(raw)}")

    new_leads = dedupe_new(raw, existing_domains)
    print(f"after dedupe vs existing: {len(new_leads)}")

    places_key = os.getenv("PLACES_API_KEY", "").strip() or None
    if args.skip_enrich:
        places_key = None

    for lead in new_leads:
        maybe_enrich(lead, places_key)
        if not args.skip_contact:
            maybe_find_contact(lead)

    new_rows = [l.to_row() for l in new_leads]
    all_rows = existing_rows + new_rows
    df = pd.DataFrame(all_rows, columns=COLUMNS)
    df.to_csv(out_path, index=False)

    qualified = sum(1 for r in new_rows if r.get("ad_evidence_url"))
    print(
        f"wrote {len(all_rows)} rows total → {out_path} "
        f"({len(new_rows)} new this run, {qualified} with ad evidence)"
    )
    return 0


def main() -> int:
    try:
        return asyncio.run(amain())
    except KeyboardInterrupt:
        print("interrupted")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
