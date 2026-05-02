"""Google Places enrichment.

Used as a fallback to fill in website / address / phone for an advertiser
when the ad source didn't expose a destination URL. Hits the Places API
Text Search + Place Details endpoints.

Requires PLACES_API_KEY in the environment. Returns ``{}`` when no key is
set or the lookup fails — callers must treat enrichment as best-effort.
"""

from __future__ import annotations

import os
from typing import Any

import httpx


PLACES_TEXT_SEARCH = "https://maps.googleapis.com/maps/api/place/textsearch/json"
PLACES_DETAILS = "https://maps.googleapis.com/maps/api/place/details/json"
DETAIL_FIELDS = "website,formatted_phone_number,formatted_address,name,business_status"


def enrich_with_places(
    business_name: str,
    city: str,
    state: str = "",
    *,
    api_key: str | None = None,
    timeout: float = 8.0,
) -> dict[str, Any]:
    """Look up a business by name+location, return website/phone/address.

    Returns ``{}`` on any failure or if no API key is configured.
    """
    api_key = api_key or os.getenv("PLACES_API_KEY", "").strip()
    if not api_key or not business_name:
        return {}

    query = " ".join(part for part in [business_name, city, state] if part).strip()

    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.get(
                PLACES_TEXT_SEARCH,
                params={"query": query, "key": api_key, "region": "us"},
            )
            r.raise_for_status()
            data = r.json()
            if data.get("status") not in {"OK", "ZERO_RESULTS"}:
                return {"_error": data.get("status", "unknown"), "_message": data.get("error_message", "")}
            results = data.get("results") or []
            if not results:
                return {}
            place_id = results[0].get("place_id")
            if not place_id:
                return {}

            r2 = client.get(
                PLACES_DETAILS,
                params={
                    "place_id": place_id,
                    "fields": DETAIL_FIELDS,
                    "key": api_key,
                },
            )
            r2.raise_for_status()
            details = r2.json().get("result", {}) or {}

    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        return {"_error": str(e)}

    return {
        "website": details.get("website", "") or "",
        "phone": details.get("formatted_phone_number", "") or "",
        "address": details.get("formatted_address", "") or "",
        "business_status": details.get("business_status", "") or "",
    }
