"""Meta (Facebook) Ad Library scraper.

Meta has no public API for the Ad Library, so we drive the public search UI
with Playwright. The selectors here target the public DOM and are inherently
brittle — Meta updates their markup on a regular cadence. When this stops
returning ads, the fix is almost always: open the Ad Library in a browser,
inspect the ad-card element, and update the selectors below.

Throttled to one search every 3–5 seconds. On captcha or hard block we log
and skip, never retry.
"""

from __future__ import annotations

import asyncio
import os
import random
import re
from datetime import datetime, timezone
from typing import AsyncIterator
from urllib.parse import quote_plus, urlparse, parse_qs, unquote

from ..lib import Lead, VERTICALS, domain_of


META_SEARCH_URL = (
    "https://www.facebook.com/ads/library/?"
    "active_status=active&ad_type=all&country=US&search_type=keyword_unordered"
    "&q={q}"
)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15"
)

# CSS selectors that have been stable enough to rely on as of writing.
# If these break, the scraper will log "no cards found" and skip the query.
AD_CARD_SELECTOR = "[role='article']"
AD_LIBRARY_LINK_SELECTOR = "a[href*='/ads/library/?id=']"
EXTERNAL_LINK_SELECTOR = "a[href*='l.facebook.com/l.php']"
PAGE_NAME_SELECTOR = "a[href^='https://www.facebook.com/'] span, a[href^='/'] span"
CAPTCHA_TEXTS = re.compile(
    r"captcha|checkpoint|temporarily restricted|temporarily unavailable|"
    r"please try again later|verify it'?s you",
    re.IGNORECASE,
)


def _resolve_meta_redirect(url: str) -> str:
    """Meta wraps outbound links via l.facebook.com/l.php?u=…"""
    try:
        parsed = urlparse(url)
        if parsed.netloc.endswith("facebook.com") and parsed.path == "/l.php":
            qs = parse_qs(parsed.query)
            if "u" in qs and qs["u"]:
                return unquote(qs["u"][0])
    except Exception:
        pass
    return url


async def scrape_meta(
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
    """Run Meta Ad Library searches for a vertical+city, return found leads.

    Returns at most ``limit`` leads. Throttles between searches.
    """
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

            url = META_SEARCH_URL.format(q=quote_plus(q))
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            except PWTimeout:
                print(f"[meta] timeout loading: {q!r} — skipping")
                continue

            content = await page.content()
            if CAPTCHA_TEXTS.search(content):
                print(f"[meta] captcha/block on query {q!r} — skipping")
                continue

            try:
                await page.wait_for_selector(AD_CARD_SELECTOR, timeout=12_000)
            except PWTimeout:
                print(f"[meta] no ad cards rendered for {q!r} — skipping")
                await asyncio.sleep(random.uniform(min_delay, max_delay))
                continue

            for _ in range(4):
                await page.mouse.wheel(0, 4000)
                await asyncio.sleep(1.2)

            cards = await page.query_selector_all(AD_CARD_SELECTOR)
            for card in cards:
                if len(leads) >= limit:
                    break

                ad_link_el = await card.query_selector(AD_LIBRARY_LINK_SELECTOR)
                if not ad_link_el:
                    continue
                ad_href = await ad_link_el.get_attribute("href")
                if not ad_href:
                    continue
                ad_evidence_url = (
                    "https://www.facebook.com" + ad_href
                    if ad_href.startswith("/")
                    else ad_href
                )

                business_name = await _extract_advertiser_name(card)
                if not business_name:
                    continue
                key = business_name.strip().lower()
                if key in seen_advertisers:
                    continue
                seen_advertisers.add(key)

                website = await _extract_external_link(card)

                lead = Lead(
                    business_name=business_name.strip(),
                    vertical=vertical,
                    city=city,
                    state=state,
                    website=website,
                    ad_platform="meta",
                    ad_evidence_url=ad_evidence_url,
                    notes=f"meta search: {q}",
                    scraped_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                )
                leads.append(lead)

            await asyncio.sleep(random.uniform(min_delay, max_delay))

        await browser.close()

    return leads


async def _extract_advertiser_name(card) -> str:
    """Pull the page/advertiser name out of an ad card."""
    for sel in [
        "a[href*='facebook.com/'] strong",
        "a[role='link'] strong",
        "h3 a, h4 a",
        "a[href^='https://www.facebook.com/']:not([href*='/ads/library'])",
    ]:
        el = await card.query_selector(sel)
        if not el:
            continue
        try:
            txt = (await el.inner_text()).strip()
        except Exception:
            continue
        if txt and len(txt) < 120:
            return txt
    return ""


async def _extract_external_link(card) -> str:
    """Find the destination URL the ad clicks through to (the advertiser site)."""
    el = await card.query_selector(EXTERNAL_LINK_SELECTOR)
    if el:
        href = await el.get_attribute("href")
        if href:
            resolved = _resolve_meta_redirect(href)
            if domain_of(resolved) and "facebook.com" not in resolved:
                return resolved
    for el in await card.query_selector_all("a[href^='http']"):
        href = await el.get_attribute("href") or ""
        if "facebook.com" in href or "instagram.com" in href:
            continue
        return href
    return ""
