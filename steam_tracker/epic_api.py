"""Epic Games Store API wrappers.

Handles OAuth2 authentication (authorization code and device auth flows)
and library retrieval via the undocumented Epic Games API.
"""
from __future__ import annotations

import logging
from typing import Any

import requests

log = logging.getLogger(__name__)

_EPIC_OAUTH_URL = (
    "https://account-public-service-prod03.ol.epicgames.com"
    "/account/api/oauth/token"
)
_EPIC_LIBRARY_URL = (
    "https://library-service.live.use1a.on.epicgames.com"
    "/library/api/public/items"
)
_EPIC_CATALOG_URL = (
    "https://catalog-public-service-prod06.ol.epicgames.com"
    "/catalog/api/shared/namespace"
)
# EOS overlay / game client used by Legendary and HeroicGamesLauncher.
# This client has the 'deviceAuths CREATE' permission and is used for all
# Epic OAuth operations in SteamPulse.
_EPIC_CLIENT_ID = "34a02cf8f4414e29b15921876da36f9a"
_EPIC_CLIENT_SECRET = "daafbccc737745039dffe53d94fc76cf"
_EPIC_BASIC_AUTH = requests.auth.HTTPBasicAuth(_EPIC_CLIENT_ID, _EPIC_CLIENT_SECRET)

_EPIC_DEVICE_AUTH_BASE = (
    "https://account-public-service-prod03.ol.epicgames.com"
    "/account/api/public/account"
)


def epic_auth_with_code(
    auth_code: str,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    """Exchange an authorization code for an Epic access token.

    Args:
        auth_code: One-time authorization code from the Epic launcher.
        session: Optional requests session (uses a new one if not provided).

    Returns:
        Dict with at least ``access_token`` and ``account_id`` keys.

    Raises:
        requests.HTTPError: If the token exchange fails.
    """
    s = session or requests.Session()
    resp = s.post(
        _EPIC_OAUTH_URL,
        data={
            "grant_type": "authorization_code",
            "code": auth_code,
        },
        auth=_EPIC_BASIC_AUTH,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()  # type: ignore[no-any-return]


def epic_auth_with_refresh(
    refresh_token: str,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    """Get a new access token using a stored refresh token.

    Refresh tokens are valid for 30 days and are automatically renewed on
    each successful call.

    Args:
        refresh_token: The refresh token from a previous OAuth response.
        session: Optional requests session.

    Returns:
        Dict with at least ``access_token``, ``refresh_token``, and ``account_id``.

    Raises:
        requests.HTTPError: If the refresh fails (e.g. token expired).
    """
    s = session or requests.Session()
    resp = s.post(
        _EPIC_OAUTH_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        auth=_EPIC_BASIC_AUTH,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()  # type: ignore[no-any-return]


def epic_auth_with_device(
    device_id: str,
    account_id: str,
    secret: str,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    """Authenticate using persistent device credentials.

    Args:
        device_id: Device ID from a previous device auth registration.
        account_id: Epic account ID.
        secret: Device auth secret.
        session: Optional requests session.

    Returns:
        Dict with ``access_token`` and ``account_id``.

    Raises:
        requests.HTTPError: If authentication fails.
    """
    s = session or requests.Session()
    resp = s.post(
        _EPIC_OAUTH_URL,
        data={
            "grant_type": "device_auth",
            "device_id": device_id,
            "account_id": account_id,
            "secret": secret,
        },
        auth=_EPIC_BASIC_AUTH,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()  # type: ignore[no-any-return]


def epic_get_library(
    access_token: str,
    session: requests.Session | None = None,
) -> list[dict[str, Any]]:
    """Fetch the user's Epic Games library (all owned items).

    Handles pagination via ``nextCursor``.

    Args:
        access_token: Bearer token from a successful OAuth exchange.
        session: Optional requests session.

    Returns:
        List of library item dicts, each containing at least
        ``catalogItemId``, ``namespace``, and ``appName``.
    """
    s = session or requests.Session()
    headers = {"Authorization": f"Bearer {access_token}"}
    all_items: list[dict[str, Any]] = []
    cursor: str | None = None

    while True:
        params: dict[str, str] = {"includeMetadata": "true"}
        if cursor:
            params["cursor"] = cursor

        resp = s.get(
            _EPIC_LIBRARY_URL,
            headers=headers,
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        records = data.get("records", [])
        all_items.extend(records)

        next_cursor = data.get("responseMetadata", {}).get("nextCursor")
        if not next_cursor:
            break
        cursor = str(next_cursor)

    return all_items


# Maximum number of catalog IDs per batch request.
_CATALOG_BATCH_SIZE = 50


def _epic_client_token(
    session: requests.Session | None = None,
) -> str:
    """Obtain a short-lived client_credentials token for public catalog queries.

    Args:
        session: Optional requests session.

    Returns:
        Access token string.

    Raises:
        requests.HTTPError: If the token request fails.
    """
    s = session or requests.Session()
    resp = s.post(
        _EPIC_OAUTH_URL,
        data={"grant_type": "client_credentials"},
        auth=_EPIC_BASIC_AUTH,
        timeout=15,
    )
    resp.raise_for_status()
    return str(resp.json()["access_token"])


def epic_get_catalog_titles(
    items: list[dict[str, Any]],
    session: requests.Session | None = None,
) -> dict[str, str]:
    """Fetch real game titles from the Epic Catalog API.

    The library endpoint does not always return human-readable titles.
    This function queries the public Catalog bulk-items endpoint to
    resolve ``catalogItemId`` → title for items that need it.

    Items are grouped by ``namespace`` and batched to respect API limits.

    Args:
        items: Library item dicts, each containing ``catalogItemId``
            and ``namespace`` keys.
        session: Optional requests session.

    Returns:
        Mapping of ``catalogItemId`` → title for all successfully
        resolved items.
    """
    if not items:
        return {}

    s = session or requests.Session()

    try:
        token = _epic_client_token(s)
    except Exception:  # noqa: BLE001
        log.warning("Failed to get Epic client token for catalog API")
        return {}

    headers = {"Authorization": f"Bearer {token}"}

    # Group catalog IDs by namespace.
    by_namespace: dict[str, list[str]] = {}
    for item in items:
        ns = str(item.get("namespace", ""))
        cid = str(item.get("catalogItemId", ""))
        if ns and cid:
            by_namespace.setdefault(ns, []).append(cid)

    result: dict[str, str] = {}

    for ns, cids in by_namespace.items():
        # Process in batches of _CATALOG_BATCH_SIZE.
        for i in range(0, len(cids), _CATALOG_BATCH_SIZE):
            batch = cids[i : i + _CATALOG_BATCH_SIZE]
            url = f"{_EPIC_CATALOG_URL}/{ns}/bulk/items"
            try:
                resp = s.get(
                    url,
                    params={"id": ",".join(batch), "country": "US"},
                    headers=headers,
                    timeout=15,
                )
                resp.raise_for_status()
            except Exception:  # noqa: BLE001
                log.debug("Catalog API failed for ns=%s batch=%d", ns, i)
                continue

            data = resp.json()
            for _key, val in data.items():
                title = val.get("title")
                item_id = val.get("id", _key)
                if isinstance(title, str) and title.strip():
                    result[str(item_id)] = title.strip()

    return result
