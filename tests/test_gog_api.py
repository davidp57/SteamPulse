"""Tests for steam_tracker.gog_api — GOG Galaxy API wrappers."""
from __future__ import annotations

import pytest
import requests
import responses as resp_mock

from steam_tracker.gog_api import (
    GOG_EMBED_BASE,
    GOG_TOKEN_URL,
    GogProduct,
    GogToken,
    gog_auth_with_code,
    gog_auth_with_refresh,
    gog_get_all_products,
    gog_get_owned_ids,
    gog_get_products_page,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TOKEN_RESP = {
    "access_token": "access_abc",
    "refresh_token": "refresh_xyz",
    "expires_in": 3600,
    "token_type": "bearer",
    "user_id": "123456",
}

_PRODUCTS_PAGE_1 = {
    "products": [
        {
            "id": 1001,
            "title": "The Witcher 3",
            "image": "//images.gog.com/witcher3.webp",
            "worksOn": {"Windows": True, "Mac": False, "Linux": False},
        },
        {
            "id": 1002,
            "title": "Cyberpunk 2077",
            "image": "//images.gog.com/cp2077.webp",
            "worksOn": {"Windows": True, "Mac": False, "Linux": False},
        },
    ],
    "totalPages": 2,
    "page": 1,
}

_PRODUCTS_PAGE_2 = {
    "products": [
        {
            "id": 1003,
            "title": "Disco Elysium",
            "image": "//images.gog.com/disco.webp",
            "worksOn": {"Windows": True, "Mac": True, "Linux": True},
        },
    ],
    "totalPages": 2,
    "page": 2,
}


# ---------------------------------------------------------------------------
# gog_auth_with_code
# ---------------------------------------------------------------------------


@resp_mock.activate
def test_gog_auth_with_code_success() -> None:
    resp_mock.add(
        resp_mock.POST,
        GOG_TOKEN_URL,
        json=_TOKEN_RESP,
        status=200,
    )
    result = gog_auth_with_code("my_auth_code")
    assert isinstance(result, GogToken)
    assert result.access_token == "access_abc"
    assert result.refresh_token == "refresh_xyz"
    assert result.expires_in == 3600


@resp_mock.activate
def test_gog_auth_with_code_http_error() -> None:
    resp_mock.add(resp_mock.POST, GOG_TOKEN_URL, json={"error": "bad_code"}, status=401)
    with pytest.raises(requests.HTTPError):
        gog_auth_with_code("bad_code")


# ---------------------------------------------------------------------------
# gog_auth_with_refresh
# ---------------------------------------------------------------------------


@resp_mock.activate
def test_gog_auth_with_refresh_success() -> None:
    resp_mock.add(
        resp_mock.POST,
        GOG_TOKEN_URL,
        json=_TOKEN_RESP,
        status=200,
    )
    result = gog_auth_with_refresh("old_refresh_token")
    assert isinstance(result, GogToken)
    assert result.access_token == "access_abc"
    assert result.refresh_token == "refresh_xyz"


@resp_mock.activate
def test_gog_auth_with_refresh_http_error() -> None:
    resp_mock.add(resp_mock.POST, GOG_TOKEN_URL, json={"error": "invalid"}, status=401)
    with pytest.raises(requests.HTTPError):
        gog_auth_with_refresh("expired_token")


# ---------------------------------------------------------------------------
# gog_get_owned_ids
# ---------------------------------------------------------------------------


@resp_mock.activate
def test_gog_get_owned_ids_success() -> None:
    resp_mock.add(
        resp_mock.GET,
        f"{GOG_EMBED_BASE}/user/data/games",
        json={"owned": [1001, 1002, 1003]},
        status=200,
    )
    ids = gog_get_owned_ids("access_abc")
    assert ids == [1001, 1002, 1003]


@resp_mock.activate
def test_gog_get_owned_ids_empty() -> None:
    resp_mock.add(
        resp_mock.GET,
        f"{GOG_EMBED_BASE}/user/data/games",
        json={"owned": []},
        status=200,
    )
    ids = gog_get_owned_ids("access_abc")
    assert ids == []


# ---------------------------------------------------------------------------
# gog_get_products_page
# ---------------------------------------------------------------------------


@resp_mock.activate
def test_gog_get_products_page_success() -> None:
    resp_mock.add(
        resp_mock.GET,
        f"{GOG_EMBED_BASE}/account/getFilteredProducts",
        json=_PRODUCTS_PAGE_1,
        status=200,
    )
    page = gog_get_products_page("access_abc", page=1)
    assert page.total_pages == 2
    assert page.page == 1
    assert len(page.products) == 2
    assert page.products[0].title == "The Witcher 3"
    assert page.products[0].id == 1001


@resp_mock.activate
def test_gog_get_products_page_fields() -> None:
    resp_mock.add(
        resp_mock.GET,
        f"{GOG_EMBED_BASE}/account/getFilteredProducts",
        json=_PRODUCTS_PAGE_1,
        status=200,
    )
    page = gog_get_products_page("access_abc", page=1)
    p = page.products[1]
    assert isinstance(p, GogProduct)
    assert p.id == 1002
    assert p.title == "Cyberpunk 2077"
    assert p.image == "//images.gog.com/cp2077.webp"


# ---------------------------------------------------------------------------
# gog_get_all_products (pagination)
# ---------------------------------------------------------------------------


@resp_mock.activate
def test_gog_get_all_products_paginated() -> None:
    resp_mock.add(
        resp_mock.GET,
        f"{GOG_EMBED_BASE}/account/getFilteredProducts",
        json=_PRODUCTS_PAGE_1,
        status=200,
    )
    resp_mock.add(
        resp_mock.GET,
        f"{GOG_EMBED_BASE}/account/getFilteredProducts",
        json=_PRODUCTS_PAGE_2,
        status=200,
    )
    products = gog_get_all_products("access_abc")
    assert len(products) == 3
    titles = [p.title for p in products]
    assert "The Witcher 3" in titles
    assert "Disco Elysium" in titles


@resp_mock.activate
def test_gog_get_all_products_single_page() -> None:
    single_page = {**_PRODUCTS_PAGE_1, "totalPages": 1, "page": 1}
    resp_mock.add(
        resp_mock.GET,
        f"{GOG_EMBED_BASE}/account/getFilteredProducts",
        json=single_page,
        status=200,
    )
    products = gog_get_all_products("access_abc")
    # Only 1 HTTP call should have been made
    assert len(resp_mock.calls) == 1
    assert len(products) == 2
