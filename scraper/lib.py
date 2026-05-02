"""Shared types and helpers for the prospect scraper.

Kept in one file (rather than split across sources/) so the public source
modules stay focused on a single advertising platform each.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Iterable
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup


COLUMNS = [
    "business_name",
    "vertical",
    "city",
    "state",
    "website",
    "owner_first_name",
    "email",
    "ad_platform",
    "ad_evidence_url",
    "notes",
    "scraped_at",
]


# Each vertical resolves to a list of search phrases used against Meta Ad
# Library / Google Ads Transparency. Order matters — earlier phrases run first.
VERTICALS: dict[str, list[str]] = {
    "med_spa": ["med spa", "medical spa", "botox clinic"],
    "dental": ["dentist", "dental practice", "orthodontist"],
    "personal_injury_law": [
        "personal injury lawyer",
        "injury attorney",
        "accident lawyer",
    ],
    "family_law": ["family law", "divorce attorney", "family lawyer"],
    "hvac": ["hvac", "ac repair", "heating and cooling"],
    "roofing": ["roofing", "roof repair", "roofer"],
    "solar": ["solar panel installation", "solar company"],
    "chiropractor": ["chiropractor", "chiropractic clinic"],
}


# Best-effort city → 2-letter state lookup for the priority US metros.
# Operator can extend this dict as new metros come online.
CITY_STATE: dict[str, str] = {
    "austin": "TX",
    "dallas": "TX",
    "houston": "TX",
    "san antonio": "TX",
    "fort worth": "TX",
    "phoenix": "AZ",
    "scottsdale": "AZ",
    "tucson": "AZ",
    "los angeles": "CA",
    "san diego": "CA",
    "san francisco": "CA",
    "san jose": "CA",
    "sacramento": "CA",
    "miami": "FL",
    "tampa": "FL",
    "orlando": "FL",
    "jacksonville": "FL",
    "fort lauderdale": "FL",
    "atlanta": "GA",
    "chicago": "IL",
    "denver": "CO",
    "nashville": "TN",
    "memphis": "TN",
    "charlotte": "NC",
    "raleigh": "NC",
    "seattle": "WA",
    "portland": "OR",
    "las vegas": "NV",
    "philadelphia": "PA",
    "pittsburgh": "PA",
    "new york": "NY",
    "boston": "MA",
    "minneapolis": "MN",
    "columbus": "OH",
    "cleveland": "OH",
    "detroit": "MI",
    "kansas city": "MO",
    "st louis": "MO",
    "indianapolis": "IN",
    "louisville": "KY",
    "salt lake city": "UT",
}


@dataclass
class Lead:
    business_name: str
    vertical: str
    city: str
    state: str = ""
    website: str = ""
    owner_first_name: str = ""
    email: str = ""
    ad_platform: str = ""
    ad_evidence_url: str = ""
    notes: str = ""
    scraped_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    def to_row(self) -> dict[str, str]:
        d = asdict(self)
        return {col: ("" if d.get(col) is None else d.get(col, "")) for col in COLUMNS}

    def append_note(self, note: str) -> None:
        if not note:
            return
        self.notes = f"{self.notes}; {note}" if self.notes else note


def humanize_vertical(vertical: str) -> str:
    return vertical.replace("_", " ")


_DOMAIN_STRIP_RE = re.compile(r"^(https?://)?(www\.)?", re.IGNORECASE)


def domain_of(url: str) -> str:
    """Return the registrable domain of a URL, lowercased. Empty if unparsable."""
    if not url:
        return ""
    if "://" not in url:
        url = "http://" + url
    try:
        host = urlparse(url).hostname or ""
    except ValueError:
        return ""
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


# --- Email + owner-name discovery from a public website ----------------------

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_GENERIC_LOCAL_PARTS = {
    "info",
    "hello",
    "contact",
    "support",
    "admin",
    "office",
    "appointments",
    "team",
    "sales",
    "billing",
    "frontdesk",
    "reception",
    "marketing",
    "noreply",
    "no-reply",
    "help",
    "mail",
    "inquiries",
    "hi",
}
_NAME_PATTERNS = [
    re.compile(r"\bMeet Dr\.\s+([A-Z][a-z]{2,})", re.IGNORECASE),
    re.compile(r"\bI'?m\s+Dr\.?\s+([A-Z][a-z]{2,})"),
    re.compile(r"\bHi[,!]?\s*I'?m\s+([A-Z][a-z]{2,})"),
    re.compile(r"\bMy name is\s+([A-Z][a-z]{2,})"),
    re.compile(r"\bowner\s*[,:\-]?\s*([A-Z][a-z]{2,})"),
]
_CONTACT_PATHS = [
    "",
    "/contact",
    "/contact-us",
    "/about",
    "/about-us",
    "/team",
    "/our-team",
    "/staff",
]


def find_contact(
    website: str,
    *,
    timeout: float = 8.0,
    user_agent: str = "Mozilla/5.0 (compatible; LeadFinder/1.0; +https://example.com/bot)",
) -> tuple[str, str, str]:
    """Crawl a public website for a published email and owner first name.

    Returns ``(email, owner_first_name, note)``. Any of the three may be
    empty. NEVER guesses or fabricates — only returns values found verbatim
    on the site.
    """
    if not website:
        return "", "", "no website to crawl"

    base = website.rstrip("/")
    if not base.startswith(("http://", "https://")):
        base = "https://" + base
    root_domain = domain_of(base)

    found_emails: set[str] = set()
    candidate_first_name = ""
    note_parts: list[str] = []

    headers = {"User-Agent": user_agent, "Accept-Language": "en-US,en;q=0.9"}
    try:
        client = httpx.Client(timeout=timeout, headers=headers, follow_redirects=True)
    except Exception as e:
        return "", "", f"http client init failed: {e}"

    with client:
        for path in _CONTACT_PATHS:
            url = base + path
            try:
                r = client.get(url)
            except (httpx.RequestError, httpx.HTTPError):
                continue
            if r.status_code != 200 or "text/html" not in r.headers.get(
                "content-type", ""
            ):
                continue

            soup = BeautifulSoup(r.text, "lxml")

            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.lower().startswith("mailto:"):
                    addr = href.split(":", 1)[1].split("?", 1)[0].strip()
                    if "@" in addr and "." in addr.split("@", 1)[1]:
                        found_emails.add(addr.lower())

            for m in _EMAIL_RE.findall(r.text):
                m = m.lower()
                if m.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")):
                    continue
                found_emails.add(m)

            if not candidate_first_name:
                text = soup.get_text(" ", strip=True)
                for pat in _NAME_PATTERNS:
                    hit = pat.search(text)
                    if hit:
                        candidate_first_name = hit.group(1).strip().title()
                        break

    chosen = _pick_best_email(found_emails, root_domain)

    if chosen:
        local = chosen.split("@", 1)[0]
        if local in _GENERIC_LOCAL_PARTS:
            note_parts.append(f"generic mailbox ({local}@)")
        elif not candidate_first_name and re.fullmatch(r"[a-z]{2,}", local):
            candidate_first_name = local.capitalize()
    else:
        note_parts.append("no email found on site")

    return chosen, candidate_first_name, "; ".join(note_parts)


def _pick_best_email(emails: Iterable[str], root_domain: str) -> str:
    emails = list(emails)
    if not emails:
        return ""

    on_domain = [e for e in emails if e.split("@", 1)[1] == root_domain] if root_domain else []

    def score(e: str) -> tuple[int, int, str]:
        local = e.split("@", 1)[0]
        domain_match = 1 if root_domain and e.split("@", 1)[1] == root_domain else 0
        looks_personal = 1 if re.fullmatch(r"[a-z]{2,}", local) and local not in _GENERIC_LOCAL_PARTS else 0
        return (domain_match, looks_personal, e)

    pool = on_domain or emails
    return sorted(pool, key=score, reverse=True)[0]
