"""Tests for Epic Games source plugin (EpicSource) and epic_api module."""
from __future__ import annotations

import argparse
from unittest.mock import patch

import responses as resp_mock

from steam_tracker.sources import GameSource

_EPIC_OAUTH = "https://account-public-service-prod03.ol.epicgames.com/account/api/oauth/token"
_EPIC_LIBRARY = (
    "https://library-service.live.use1a.on.epicgames.com/library/api/public/items"
)
_EPIC_DEVICE_AUTH = (
    "https://account-public-service-prod03.ol.epicgames.com"
    "/account/api/public/account/{account_id}/deviceAuth"
)

# -- Helpers ----------------------------------------------------------------


def _make_args(
    *,
    epic_auth_code: str | None = None,
    epic_refresh_token: str | None = None,
    epic_account_id: str | None = None,
    twitch_client_id: str | None = None,
    twitch_client_secret: str | None = None,
    lang: str | None = None,
    key: str = "fake_key",
    steamid: str = "76561198000000000",
) -> argparse.Namespace:
    return argparse.Namespace(
        epic_auth_code=epic_auth_code,
        epic_refresh_token=epic_refresh_token,
        epic_account_id=epic_account_id,
        twitch_client_id=twitch_client_id,
        twitch_client_secret=twitch_client_secret,
        lang=lang,
        key=key,
        steamid=steamid,
    )


def _oauth_token_response(
    account_id: str = "abc123",
    access_token: str = "epic_tok",
) -> dict[str, object]:
    return {
        "access_token": access_token,
        "account_id": account_id,
        "token_type": "bearer",
    }


def _library_response(items: list[dict[str, object]]) -> dict[str, object]:
    return {"records": items, "responseMetadata": {"nextCursor": None}}


def _library_item(
    catalog_item_id: str,
    title: str,
    namespace: str = "ns1",
) -> dict[str, object]:
    return {
        "catalogItemId": catalog_item_id,
        "namespace": namespace,
        "appName": title,
    }


# -- Protocol conformance ---------------------------------------------------


def test_epic_source_satisfies_protocol() -> None:
    from steam_tracker.sources.epic import EpicSource

    assert isinstance(EpicSource(), GameSource)


def test_epic_source_name() -> None:
    from steam_tracker.sources.epic import EpicSource

    assert EpicSource().name == "epic"


# -- CLI arguments -----------------------------------------------------------


def test_add_arguments_registers_epic_flags() -> None:
    from steam_tracker.sources.epic import EpicSource

    parser = argparse.ArgumentParser()
    EpicSource().add_arguments(parser)
    dests = {a.dest for a in parser._actions}
    assert "epic_auth_code" in dests


# -- is_enabled --------------------------------------------------------------


def test_is_enabled_false_without_args() -> None:
    from steam_tracker.sources.epic import EpicSource

    args = _make_args()
    assert EpicSource().is_enabled(args) is False


def test_is_enabled_true_with_auth_code() -> None:
    from steam_tracker.sources.epic import EpicSource

    args = _make_args(epic_auth_code="some_code")
    assert EpicSource().is_enabled(args) is True


def test_is_enabled_true_with_refresh_token() -> None:
    from steam_tracker.sources.epic import EpicSource

    args = _make_args(
        epic_refresh_token="rt1",
        epic_account_id="acc1",
    )
    assert EpicSource().is_enabled(args) is True


# -- discover_games ----------------------------------------------------------


@resp_mock.activate
def test_discover_games_with_auth_code() -> None:
    """Auth code flow: exchange code → fetch library → return games."""
    from steam_tracker.sources.epic import EpicSource

    # 1. OAuth token exchange
    resp_mock.add(
        resp_mock.POST,
        _EPIC_OAUTH,
        json=_oauth_token_response(),
    )
    # 2. Library fetch
    resp_mock.add(
        resp_mock.GET,
        _EPIC_LIBRARY,
        json=_library_response([
            _library_item("cat1", "Hades"),
            _library_item("cat2", "Celeste"),
        ]),
    )

    args = _make_args(epic_auth_code="code123")
    with patch(
        "steam_tracker.sources.epic.resolve_steam_appid", return_value=None
    ):
        games = EpicSource().discover_games(args)

    assert len(games) == 2
    assert all(g.source == "epic" for g in games)
    assert all(g.external_id.startswith("epic:") for g in games)
    names = {g.name for g in games}
    assert "Hades" in names
    assert "Celeste" in names


@resp_mock.activate
def test_discover_games_with_resolved_appid() -> None:
    """When resolver finds a Steam AppID, the game uses that appid."""
    from steam_tracker.sources.epic import EpicSource

    resp_mock.add(resp_mock.POST, _EPIC_OAUTH, json=_oauth_token_response())
    resp_mock.add(
        resp_mock.GET,
        _EPIC_LIBRARY,
        json=_library_response([_library_item("cat1", "Hades")]),
    )

    args = _make_args(epic_auth_code="code123")
    with patch(
        "steam_tracker.sources.epic.resolve_steam_appid", return_value=1145360
    ):
        games = EpicSource().discover_games(args)

    assert len(games) == 1
    assert games[0].appid == 1145360
    assert games[0].external_id == "epic:cat1"
    assert games[0].source == "epic"


@resp_mock.activate
def test_discover_games_unresolved_gets_hash_appid() -> None:
    """When no Steam AppID is found, generate a deterministic hash-based appid."""
    from steam_tracker.sources.epic import EpicSource

    resp_mock.add(resp_mock.POST, _EPIC_OAUTH, json=_oauth_token_response())
    resp_mock.add(
        resp_mock.GET,
        _EPIC_LIBRARY,
        json=_library_response([_library_item("cat_unique", "SomeEpicExclusive")]),
    )

    args = _make_args(epic_auth_code="code123")
    with patch(
        "steam_tracker.sources.epic.resolve_steam_appid", return_value=None
    ):
        games = EpicSource().discover_games(args)

    assert len(games) == 1
    g = games[0]
    # Hash-based appid in the reserved range (2_000_000_000+)
    assert g.appid >= 2_000_000_000
    assert g.external_id == "epic:cat_unique"


@resp_mock.activate
def test_discover_games_auth_failure_returns_empty() -> None:
    """If Epic auth fails, discover_games returns an empty list gracefully."""
    from steam_tracker.sources.epic import EpicSource

    resp_mock.add(resp_mock.POST, _EPIC_OAUTH, status=401)

    args = _make_args(epic_auth_code="bad_code")
    games = EpicSource().discover_games(args)
    assert games == []


@resp_mock.activate
def test_discover_games_empty_library() -> None:
    """An empty Epic library returns an empty game list."""
    from steam_tracker.sources.epic import EpicSource

    resp_mock.add(resp_mock.POST, _EPIC_OAUTH, json=_oauth_token_response())
    resp_mock.add(
        resp_mock.GET,
        _EPIC_LIBRARY,
        json=_library_response([]),
    )

    args = _make_args(epic_auth_code="code123")
    games = EpicSource().discover_games(args)
    assert games == []


@resp_mock.activate
def test_discover_games_library_api_error_returns_empty() -> None:
    """If the library API fails, return empty gracefully."""
    from steam_tracker.sources.epic import EpicSource

    resp_mock.add(resp_mock.POST, _EPIC_OAUTH, json=_oauth_token_response())
    resp_mock.add(resp_mock.GET, _EPIC_LIBRARY, status=500)

    args = _make_args(epic_auth_code="code123")
    games = EpicSource().discover_games(args)
    assert games == []


# -- epic_api module tests ---------------------------------------------------


@resp_mock.activate
def test_epic_auth_with_code() -> None:
    """Authorization code exchange returns access_token + account_id."""
    from steam_tracker.epic_api import epic_auth_with_code

    resp_mock.add(
        resp_mock.POST,
        _EPIC_OAUTH,
        json=_oauth_token_response(account_id="myacc", access_token="tok123"),
    )
    result = epic_auth_with_code("code_value")
    assert result["access_token"] == "tok123"
    assert result["account_id"] == "myacc"


@resp_mock.activate
def test_epic_auth_with_code_failure() -> None:
    """Auth failure raises an exception."""
    from steam_tracker.epic_api import epic_auth_with_code

    resp_mock.add(resp_mock.POST, _EPIC_OAUTH, status=401)
    try:
        epic_auth_with_code("bad_code")
        msg = "Expected an exception"
        raise AssertionError(msg)
    except Exception:  # noqa: BLE001
        pass


@resp_mock.activate
def test_epic_get_library() -> None:
    """Library API returns parsed records."""
    from steam_tracker.epic_api import epic_get_library

    resp_mock.add(
        resp_mock.GET,
        _EPIC_LIBRARY,
        json=_library_response([
            _library_item("c1", "Game One"),
            _library_item("c2", "Game Two"),
        ]),
    )
    items = epic_get_library("tok123")
    assert len(items) == 2
    assert items[0]["catalogItemId"] == "c1"
    assert items[1]["appName"] == "Game Two"


@resp_mock.activate
def test_epic_get_library_pagination() -> None:
    """Library API handles pagination via nextCursor."""
    from steam_tracker.epic_api import epic_get_library

    # Page 1 → has cursor
    resp_mock.add(
        resp_mock.GET,
        _EPIC_LIBRARY,
        json={
            "records": [_library_item("c1", "Game One")],
            "responseMetadata": {"nextCursor": "cursor_abc"},
        },
    )
    # Page 2 → no cursor (end)
    resp_mock.add(
        resp_mock.GET,
        _EPIC_LIBRARY,
        json=_library_response([_library_item("c2", "Game Two")]),
    )
    items = epic_get_library("tok123")
    assert len(items) == 2


@resp_mock.activate
def test_epic_get_library_empty() -> None:
    """Empty library returns empty list."""
    from steam_tracker.epic_api import epic_get_library

    resp_mock.add(resp_mock.GET, _EPIC_LIBRARY, json=_library_response([]))
    items = epic_get_library("tok123")
    assert items == []
