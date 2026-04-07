"""GOG Galaxy API wrappers.

Handles OAuth2 authentication (authorization code and refresh token flows)
and library / product retrieval via the unofficial GOG embed API.

Note on credentials:
    The ``GOG_CLIENT_ID`` and ``GOG_CLIENT_SECRET`` constants are the public
    client credentials used by the GOG Galaxy desktop client.  They are
    widely known from reverse-engineering of GOG Galaxy and are safe to
    include here; they carry no user-level permissions on their own.
"""

from __future__ import annotations

import logging
import os
from urllib.parse import urlencode

import requests
from pydantic import BaseModel

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# GOG Galaxy desktop client credentials (publicly known from reverse engineering).
# Override via ``STEAMPULSE_GOG_CLIENT_SECRET`` env variable if needed.
GOG_CLIENT_ID = os.environ.get("STEAMPULSE_GOG_CLIENT_ID", "46899977096215655")
GOG_CLIENT_SECRET = os.environ.get(
    "STEAMPULSE_GOG_CLIENT_SECRET",
    "9d85c43b1482497dbbce61f6e4aa173a433796eeae2ca8c5f6129f2dc4de46d9",
)

# After the user logs in at GOG_AUTH_URL they are redirected to
# embed.gog.com/on_login_success and the URL contains ``?code=…``.
GOG_AUTH_URL = "https://auth.gog.com/auth?" + urlencode(
    {
        "client_id": GOG_CLIENT_ID,
        "redirect_uri": "https://embed.gog.com/on_login_success?origin=client",
        "response_type": "code",
        "layout": "client2",
    }
)

GOG_TOKEN_URL = "https://auth.gog.com/token"
GOG_EMBED_BASE = "https://embed.gog.com"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class GogToken(BaseModel):
    """OAuth2 token response from the GOG auth endpoint."""

    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str
    user_id: str = ""


class GogProduct(BaseModel):
    """A single product (game) from the GOG library."""

    id: int
    title: str
    image: str = ""


class GogProductsPage(BaseModel):
    """A paginated response from the GOG ``getFilteredProducts`` endpoint."""

    products: list[GogProduct]
    total_pages: int
    page: int


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def gog_auth_with_code(
    auth_code: str,
    session: requests.Session | None = None,
) -> GogToken:
    """Exchange an authorization code for GOG access and refresh tokens.

    The user first visits :data:`GOG_AUTH_URL` in a browser, logs in, and
    copies the ``code`` query parameter from the redirect URL.

    Args:
        auth_code: One-time authorization code from the GOG login redirect URL.
        session: Optional requests session (a new one is created if not given).

    Returns:
        :class:`GogToken` containing access and refresh tokens.

    Raises:
        requests.HTTPError: If the token exchange fails.
    """
    s = session or requests.Session()
    resp = s.post(
        GOG_TOKEN_URL,
        data={
            "client_id": GOG_CLIENT_ID,
            "client_secret": GOG_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": "https://embed.gog.com/on_login_success?origin=client",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return GogToken.model_validate(resp.json())


def gog_auth_with_refresh(
    refresh_token: str,
    session: requests.Session | None = None,
) -> GogToken:
    """Get a new access token using a stored refresh token.

    GOG refresh tokens are long-lived and are automatically rotated on
    each successful call.

    Args:
        refresh_token: The refresh token from a previous OAuth response.
        session: Optional requests session.

    Returns:
        :class:`GogToken` with a fresh access token and rotated refresh token.

    Raises:
        requests.HTTPError: If the refresh fails (e.g. token expired).
    """
    s = session or requests.Session()
    resp = s.post(
        GOG_TOKEN_URL,
        data={
            "client_id": GOG_CLIENT_ID,
            "client_secret": GOG_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return GogToken.model_validate(resp.json())


# ---------------------------------------------------------------------------
# Library endpoints
# ---------------------------------------------------------------------------


def gog_get_owned_ids(
    access_token: str,
    session: requests.Session | None = None,
) -> list[int]:
    """Return the list of owned product IDs for the authenticated user.

    Args:
        access_token: A valid GOG access token.
        session: Optional requests session.

    Returns:
        List of integer GOG product IDs.

    Raises:
        requests.HTTPError: On HTTP error.
    """
    s = session or requests.Session()
    resp = s.get(
        f"{GOG_EMBED_BASE}/user/data/games",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    resp.raise_for_status()
    return list(resp.json().get("owned", []))


def gog_get_products_page(
    access_token: str,
    page: int = 1,
    session: requests.Session | None = None,
) -> GogProductsPage:
    """Fetch one page of the user's product library.

    Args:
        access_token: A valid GOG access token.
        page: 1-indexed page number.
        session: Optional requests session.

    Returns:
        :class:`GogProductsPage` with the products and pagination info.

    Raises:
        requests.HTTPError: On HTTP error.
    """
    s = session or requests.Session()
    resp = s.get(
        f"{GOG_EMBED_BASE}/account/getFilteredProducts",
        params={"mediaType": 1, "page": page},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    resp.raise_for_status()
    raw = resp.json()
    products = [GogProduct.model_validate(p) for p in raw.get("products", [])]
    return GogProductsPage(
        products=products,
        total_pages=raw.get("totalPages", 1),
        page=raw.get("page", page),
    )


def gog_get_all_products(
    access_token: str,
    session: requests.Session | None = None,
) -> list[GogProduct]:
    """Fetch the complete product library by iterating over all pages.

    Args:
        access_token: A valid GOG access token.
        session: Optional requests session.

    Returns:
        Flat list of all :class:`GogProduct` items across all pages.

    Raises:
        requests.HTTPError: On HTTP error from any paginated request.
    """
    s = session or requests.Session()
    first_page = gog_get_products_page(access_token, page=1, session=s)
    all_products: list[GogProduct] = list(first_page.products)

    for page_num in range(2, first_page.total_pages + 1):
        page = gog_get_products_page(access_token, page=page_num, session=s)
        all_products.extend(page.products)
        log.debug(
            "GOG products page %d/%d: fetched %d items",
            page_num,
            first_page.total_pages,
            len(page.products),
        )

    return all_products
