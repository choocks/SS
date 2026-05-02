"""Google Ads Transparency Center scraper.

Like Meta's Ad Library, this site has no public API and is heavily
JS-rendered, so we use Playwright. Selectors are best-effort and brittle —
when they break, open https://adstransparency.google.com/, search for a
known advertiser, inspect the result card, and update the selectors.
"""

from __future__ import annotations

import asyncio
import os
import random
import re
from datetime import datetime, timezone
from urllib.parse import quote_plus

from ..lib import Lead, VERTICALS, domain_of


GOOGLE_ATC_URL = (
    "https://adstransparency.google.com/?region=US"
    "&query={q}"
)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15"
)

ADVERTISER_CARD_SELECTOR = "a[href*='/advertiser/']"
ADVERTISER_NAME_SELECTOR = "div[role='heading'], h3, .advertiser-name"
BLOCK_TEXTS = re.compile(
    r"unusual traffic|verify you'?re human|temporarily unavailable",
    re.IGNORECASE,
)


async def scrape_google_ads(
    vertical: str,
    city: str,
    state: str,
    limit: int,
    *,
    headless: bool = True,
    min_delay: float | None = None,
    max_delay: float | None = None,
    user_agent: str | None = None,
) -> list[Lead]:
    """Search Google Ads Transparency Center for the given vertical+city."""
    try:
        from playwright.async_api import async_playwright, TimeoutError as PWTimeout
    except ImportError as e:
        raise RuntimeError(
            "Playwright is not installed. Run: pip install -r scraper/requirements.txt "
            "&& python -m playwright install chromium"
        ) from e

    min_delay = min_delay if min_delay is not None else float(
        os.getenv("SCRAPER_MIN_DELAY_SECONDS", "3")
    )
    max_delay = max_delay if max_delay is not None else float(
        os.getenv("SCRAPER_MAX_DELAY_SECONDS", "5")
    )
    ua = user_agent or os.getenv("SCRAPER_USER_AGENT") or DEFAULT_USER_AGENT

    if vertical not in VERTICALS:
        raise ValueError(f"unknown vertical: {vertical}")

    queries = [f"{phrase} {city}".strip() for phrase in VERTICALS[vertical]]
    leads: list[Lead] = []
    seen_advertisers: set[str] = set()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent=ua,
            locale="en-US",
            viewport={"width": 1280, "height": 900},
            ignore_https_errors=True,
        )
        page = await context.new_page()

        for q in queries:
            if len(leads) >= limit:
                break

            url = GOOGLE_ATC_URL.format(q=quote_plus(q))
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            except PWTimeout:
                print(f"[google] timeout loading: {q!r} — skipping")
                continue

            content = await page.content()
            if BLOCK_TEXTS.search(content):
                print(f"[google] block on query {q!r} — skipping")
                continue

            try:
                await page.wait_for_selector(
                    ADVERTISER_CARD_SELECTOR, timeout=12_000
                )
            except PWTimeout:
                print(f"[google] no advertisers rendered for {q!r} — skipping")
                await asyncio.sleep(random.uniform(min_delay, max_delay))
                continue

            for _ in range(3):
                await page.mouse.wheel(0, 3000)
                await asyncio.sleep(1.0)

            cards = await page.query_selector_all(ADVERTISER_CARD_SELECTOR)
            for card in cards:
                if len(leads) >= limit:
                    break

                href = await card.get_attribute("href") or ""
                if "/advertiser/" not in href:
                    continue
                ad_evidence_url = (
                    "https://adstransparency.google.com" + href
                    if href.startswith("/")
                    else href
                )

                name = ""
                for sel in [ADVERTISER_NAME_SELECTOR, "span"]:
                    el = await card.query_selector(sel)
                    if not el:
                        continue
                    try:
                        txt = (await el.inner_text()).strip()
                    except Exception:
                        continue
                    if txt and len(txt) < 120:
                        name = txt
                        break

                if not name:
                    continue
                key = name.strip().lower()
                if key in seen_advertisers:
                    continue
                seen_advertisers.add(key)

                leads.append(
                    Lead(
                        business_name=name,
                        vertical=vertical,
                        city=city,
                        state=state,
                        website="",
                        ad_platform="google",
                        ad_evidence_url=ad_evidence_url,
                        notes=f"google atc search: {q}",
                        scraped_at=datetime.now(timezone.utc).isoformat(
                            timespec="seconds"
                        ),
                    )
                )

            await asyncio.sleep(random.uniform(min_delay, max_delay))

        await browser.close()

    return leads
