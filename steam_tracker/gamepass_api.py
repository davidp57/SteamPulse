"""Xbox Game Pass catalog API wrappers.

Fetches the list of PC Game Pass titles from Microsoft's public catalog
endpoints — no authentication is required.

Two calls are made:
1. ``catalog.gamepass.com/sigls/v2`` — returns the list of store IDs in the
   PC Game Pass catalog.
2. ``displaycatalog.mp.microsoft.com/v7.0/products`` — returns display info
   (titles) for a given set of store IDs, queried in batches.
"""

from __future__ import annotations

import logging

import requests

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Product group ID for PC Game Pass in the Game Pass catalog
GAMEPASS_PC_CATALOG_ID = "fdd9e2a7-0fee-49f6-ad69-4354098401ff"

GAMEPASS_CATALOG_URL = "https://catalog.gamepass.com/sigls/v2"
MS_CATALOG_URL = "https://displaycatalog.mp.microsoft.com/v7.0/products"

# Microsoft catalog detail endpoint has an unpublished limit; 20 is safe.
_DETAIL_BATCH_SIZE = 20


# ---------------------------------------------------------------------------
# API functions
# ---------------------------------------------------------------------------


def gamepass_get_catalog_ids(
    market: str = "US",
    lang: str = "en-us",
    session: requests.Session | None = None,
) -> list[str]:
    """Return all store product IDs listed in the PC Game Pass catalog.

    Entries in the catalog response that lack an ``id`` field are silently
    skipped (the first entry is typically a metadata object).

    Args:
        market: Two-letter market/country code (default ``"US"``).
        lang: BCP-47 language code (default ``"en-us"``).
        session: Optional requests session.

    Returns:
        List of Microsoft Store product ID strings.

    Raises:
        requests.HTTPError: On HTTP error.
    """
    s = session or requests.Session()
    resp = s.get(
        GAMEPASS_CATALOG_URL,
        params={
            "id": GAMEPASS_PC_CATALOG_ID,
            "language": lang,
            "market": market,
        },
        timeout=20,
    )
    resp.raise_for_status()
    entries: list[dict[str, object]] = resp.json()
    return [str(entry["id"]) for entry in entries if "id" in entry]


def gamepass_get_titles(
    store_ids: list[str],
    market: str = "US",
    lang: str = "en-us",
    session: requests.Session | None = None,
) -> dict[str, str]:
    """Return a mapping of store product ID → product title.

    Queries the Microsoft display catalog in batches of :data:`_DETAIL_BATCH_SIZE`.
    Products with an empty ``LocalizedProperties`` list are skipped.

    Args:
        store_ids: List of Microsoft Store product IDs.
        market: Two-letter market/country code (default ``"US"``).
        lang: BCP-47 language code (default ``"en-us"``).
        session: Optional requests session.

    Returns:
        Dict mapping each resolved store ID to its localized product title.

    Raises:
        requests.HTTPError: On HTTP error from any batch request.
    """
    if not store_ids:
        return {}

    s = session or requests.Session()
    result: dict[str, str] = {}

    for offset in range(0, len(store_ids), _DETAIL_BATCH_SIZE):
        batch = store_ids[offset : offset + _DETAIL_BATCH_SIZE]
        resp = s.get(
            MS_CATALOG_URL,
            params={
                "bigIds": ",".join(batch),
                "market": market,
                "languages": lang,
            },
            timeout=20,
        )
        resp.raise_for_status()

        for product in resp.json().get("Products", []):
            pid = product.get("ProductId", "")
            localized = product.get("LocalizedProperties", [])
            if not localized:
                log.debug("Game Pass product %s has no localized title, skipping", pid)
                continue
            title = localized[0].get("ProductTitle", "")
            if pid and title:
                result[pid] = title

    return result
