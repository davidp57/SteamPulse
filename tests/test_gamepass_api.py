"""Tests for steam_tracker.gamepass_api — Xbox Game Pass catalog API wrappers."""
from __future__ import annotations

import pytest
import requests
import responses as resp_mock

from steam_tracker.gamepass_api import (
    GAMEPASS_CATALOG_URL,
    MS_CATALOG_URL,
    gamepass_get_catalog_ids,
    gamepass_get_titles,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CATALOG_RESP = [
    {"id": "9NBLGGH4NNS1", "language": "en-us"},
    {"id": "9N5TD916686K", "language": "en-us"},
    {"id": "9NZVL19N7CPS", "language": "en-us"},
    # sigls/v2 also contains a non-product entry with no id key — must be filtered
    {"language": "en-us"},
]

_DETAIL_RESP = {
    "Products": [
        {
            "ProductId": "9NBLGGH4NNS1",
            "LocalizedProperties": [{"ProductTitle": "Halo Infinite"}],
        },
        {
            "ProductId": "9N5TD916686K",
            "LocalizedProperties": [{"ProductTitle": "Forza Horizon 5"}],
        },
        {
            "ProductId": "9NZVL19N7CPS",
            "LocalizedProperties": [{"ProductTitle": "Sea of Thieves"}],
        },
    ]
}


# ---------------------------------------------------------------------------
# gamepass_get_catalog_ids
# ---------------------------------------------------------------------------


@resp_mock.activate
def test_gamepass_get_catalog_ids_success() -> None:
    resp_mock.add(
        resp_mock.GET,
        GAMEPASS_CATALOG_URL,
        json=_CATALOG_RESP,
        status=200,
    )
    ids = gamepass_get_catalog_ids()
    # Entry without 'id' key must be filtered out
    assert ids == ["9NBLGGH4NNS1", "9N5TD916686K", "9NZVL19N7CPS"]


@resp_mock.activate
def test_gamepass_get_catalog_ids_empty() -> None:
    resp_mock.add(resp_mock.GET, GAMEPASS_CATALOG_URL, json=[], status=200)
    ids = gamepass_get_catalog_ids()
    assert ids == []


@resp_mock.activate
def test_gamepass_get_catalog_ids_http_error() -> None:
    resp_mock.add(resp_mock.GET, GAMEPASS_CATALOG_URL, status=503)
    with pytest.raises(requests.HTTPError):
        gamepass_get_catalog_ids()


# ---------------------------------------------------------------------------
# gamepass_get_titles
# ---------------------------------------------------------------------------


@resp_mock.activate
def test_gamepass_get_titles_success() -> None:
    resp_mock.add(
        resp_mock.GET,
        MS_CATALOG_URL,
        json=_DETAIL_RESP,
        status=200,
    )
    titles = gamepass_get_titles(["9NBLGGH4NNS1", "9N5TD916686K", "9NZVL19N7CPS"])
    assert titles["9NBLGGH4NNS1"] == "Halo Infinite"
    assert titles["9N5TD916686K"] == "Forza Horizon 5"
    assert titles["9NZVL19N7CPS"] == "Sea of Thieves"


@resp_mock.activate
def test_gamepass_get_titles_batched() -> None:
    """More than _DETAIL_BATCH_SIZE IDs must result in multiple HTTP requests."""
    from steam_tracker.gamepass_api import _DETAIL_BATCH_SIZE

    # Build 2*batch+1 fake IDs
    n = _DETAIL_BATCH_SIZE * 2 + 1
    store_ids = [f"FAKEID{i:04d}" for i in range(n)]

    # Respond to each batch with an empty product list (we only care about call count)
    resp_mock.add(resp_mock.GET, MS_CATALOG_URL, json={"Products": []}, status=200)
    resp_mock.add(resp_mock.GET, MS_CATALOG_URL, json={"Products": []}, status=200)
    resp_mock.add(resp_mock.GET, MS_CATALOG_URL, json={"Products": []}, status=200)

    gamepass_get_titles(store_ids)

    # Must have fired exactly 3 requests (ceil(n / batch_size) = 3)
    assert len(resp_mock.calls) == 3


@resp_mock.activate
def test_gamepass_get_titles_empty_input() -> None:
    titles = gamepass_get_titles([])
    assert titles == {}
    # No HTTP call should be made for empty input
    assert len(resp_mock.calls) == 0


@resp_mock.activate
def test_gamepass_get_titles_missing_product_title() -> None:
    """Products with no LocalizedProperties entry must be skipped gracefully."""
    resp_mock.add(
        resp_mock.GET,
        MS_CATALOG_URL,
        json={"Products": [{"ProductId": "FAKEID0001", "LocalizedProperties": []}]},
        status=200,
    )
    titles = gamepass_get_titles(["FAKEID0001"])
    # Product with empty LocalizedProperties → no entry in result
    assert "FAKEID0001" not in titles
