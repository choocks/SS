"""Pipeline smoke test that doesn't depend on Meta/Google egress.

Constructs a handful of Lead objects with real public websites, runs them
through the same enrichment + contact-finder + CSV-append + dedupe path
that scraper/run.py uses. Exists to validate the non-scrape half of the
pipeline in environments where facebook.com is blocked.

Usage: python scraper/_smoke.py --out /tmp/prospects_smoke.csv
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

_HERE = Path(__file__).resolve().parent
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

from scraper.lib import COLUMNS, Lead, find_contact  # noqa: E402
from scraper.run import dedupe_new, load_existing  # noqa: E402


SAMPLE_LEADS = [
    Lead(
        business_name="Python Software Foundation",
        vertical="med_spa",  # vertical is irrelevant for this smoke test
        city="Wilmington",
        state="DE",
        website="https://www.python.org",
        ad_platform="meta",
        ad_evidence_url="https://www.facebook.com/ads/library/?id=00000000",
        notes="smoke test fixture",
    ),
    Lead(
        business_name="Example Domain",
        vertical="med_spa",
        city="Los Angeles",
        state="CA",
        website="https://www.example.com",
        ad_platform="google",
        ad_evidence_url="https://adstransparency.google.com/advertiser/SAMPLE",
        notes="smoke test fixture",
    ),
    Lead(
        business_name="GitHub Inc",
        vertical="med_spa",
        city="San Francisco",
        state="CA",
        website="https://github.com",
        ad_platform="meta",
        ad_evidence_url="https://www.facebook.com/ads/library/?id=00000001",
        notes="smoke test fixture",
    ),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/prospects_smoke.csv")
    args = ap.parse_args()

    out = Path(args.out)

    existing_rows, existing_domains = load_existing(out)
    print(f"existing rows: {len(existing_rows)} (domains: {len(existing_domains)})")

    new = dedupe_new(list(SAMPLE_LEADS), existing_domains)
    print(f"after dedupe vs existing: {len(new)}")

    for lead in new:
        email, first_name, note = find_contact(lead.website)
        if email:
            lead.email = email
        if first_name and not lead.owner_first_name:
            lead.owner_first_name = first_name
        lead.append_note(note or "")
        print(
            f"  {lead.business_name:30s}  email={lead.email or '-':30s}  "
            f"owner={lead.owner_first_name or '-':12s}  note={note}"
        )

    rows = existing_rows + [l.to_row() for l in new]
    pd.DataFrame(rows, columns=COLUMNS).to_csv(out, index=False)
    print(f"wrote {len(rows)} rows → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
