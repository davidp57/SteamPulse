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


def epic_create_device_auth(
    access_token: str,
    account_id: str,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    """Register a new set of persistent device credentials for an authenticated account.

    Call this once after ``epic_auth_with_code`` to obtain ``device_id``, ``account_id``,
    and ``secret`` credentials that allow headless re-authentication on future runs without
    requiring the user to re-enter an auth code.

    Args:
        access_token: A valid Bearer access token from ``epic_auth_with_code``.
        account_id: The Epic account ID returned by ``epic_auth_with_code``.
        session: Optional requests session.

    Returns:
        Dict with at least ``device_id``, ``accountId``, and ``secret``.

    Raises:
        requests.HTTPError: If the request fails.
    """
    s = session or requests.Session()
    resp = s.post(
        f"{_EPIC_DEVICE_AUTH_BASE}/{account_id}/deviceAuth",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    if not resp.ok:
        raise requests.HTTPError(
            f"{resp.status_code} {resp.reason} — body: {resp.text}",
            response=resp,
        )
    data: dict[str, Any] = resp.json()
    # The API returns camelCase keys; normalise to snake_case for consistency.
    if "deviceId" in data and "device_id" not in data:
        data["device_id"] = data["deviceId"]
    if "accountId" in data and "account_id" not in data:
        data["account_id"] = data["accountId"]
    return data


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
