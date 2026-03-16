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
# The launcher client credentials used by Legendary / HeroicGamesLauncher.
_EPIC_CLIENT_ID = "34a02cf8f4414e29b15921876da36f9a"
_EPIC_CLIENT_SECRET = "daafbccc737745039dffe53d94fc76cf"
_EPIC_BASIC_AUTH = requests.auth.HTTPBasicAuth(_EPIC_CLIENT_ID, _EPIC_CLIENT_SECRET)


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
