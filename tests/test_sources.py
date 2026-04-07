"""Tests for steam_tracker.sources.

Covers the GameSource protocol, SteamSource, EpicSource, GogSource, and GamePassSource.
"""
from __future__ import annotations

import argparse

import pytest
import requests
import responses as resp_mock

from steam_tracker.models import SYNTHETIC_APPID_BASE, OwnedGame
from steam_tracker.sources import GameSource, get_all_sources
from steam_tracker.sources.epic import EpicSource
from steam_tracker.sources.gamepass import GamePassSource
from steam_tracker.sources.gog import GogSource
from steam_tracker.sources.steam import SteamSource

_STEAM_API = "https://api.steampowered.com"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_args(
    *,
    key: str = "fake_key",
    steamid: str = "76561198000000000",
    no_wishlist: bool = False,
    followed: bool = False,
    lang: str | None = None,
) -> argparse.Namespace:
    """Build a minimal argparse.Namespace for SteamSource tests."""
    return argparse.Namespace(
        key=key,
        steamid=steamid,
        no_wishlist=no_wishlist,
        followed=followed,
        lang=lang,
    )


def _owned_response(appids: list[int]) -> dict:  # type: ignore[type-arg]
    return {
        "response": {
            "games": [
                {"appid": appid, "name": f"Game {appid}", "playtime_forever": 0}
                for appid in appids
            ]
        }
    }


def _wishlist_response(appids: list[int]) -> dict:  # type: ignore[type-arg]
    return {"response": {"items": [{"appid": appid} for appid in appids]}}


def _followed_response(appids: list[int]) -> dict:  # type: ignore[type-arg]
    return {"response": {"games": [{"appid": appid} for appid in appids]}}


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_steam_source_name() -> None:
    assert SteamSource().name == "steam"


def test_steam_source_is_runtime_checkable() -> None:
    assert isinstance(SteamSource(), GameSource)


def test_custom_source_satisfies_protocol() -> None:
    """Any class with the right shape satisfies GameSource at runtime."""

    class FakeSource:
        name = "fake"
        source_labels: frozenset[str] = frozenset({"fake"})

        def add_arguments(self, parser: argparse.ArgumentParser) -> None:
            pass

        def is_enabled(self, args: argparse.Namespace) -> bool:
            return True

        def discover_games(self, args: argparse.Namespace) -> list[OwnedGame]:
            return []

    assert isinstance(FakeSource(), GameSource)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_get_all_sources_contains_steam_source() -> None:
    sources = get_all_sources()
    assert any(isinstance(s, SteamSource) for s in sources)


def test_get_all_sources_returns_new_list_each_time() -> None:
    """Callers modifying the returned list must not affect the registry."""
    a = get_all_sources()
    b = get_all_sources()
    a.clear()
    assert len(b) > 0


# ---------------------------------------------------------------------------
# CLI argument registration
# ---------------------------------------------------------------------------


def test_steam_source_registers_key_and_steamid() -> None:
    parser = argparse.ArgumentParser()
    SteamSource().add_arguments(parser)
    dests = {a.dest for a in parser._actions}
    assert "key" in dests
    assert "steamid" in dests


def test_steam_source_registers_no_wishlist_and_followed() -> None:
    parser = argparse.ArgumentParser()
    SteamSource().add_arguments(parser)
    dests = {a.dest for a in parser._actions}
    assert "no_wishlist" in dests
    assert "followed" in dests


def test_steam_source_is_enabled_always_true() -> None:
    args = _make_args()
    assert SteamSource().is_enabled(args) is True


# ---------------------------------------------------------------------------
# discover_games — owned library
# ---------------------------------------------------------------------------


@resp_mock.activate
def test_discover_games_returns_owned_games() -> None:
    resp_mock.add(
        resp_mock.GET,
        f"{_STEAM_API}/IPlayerService/GetOwnedGames/v1/",
        json=_owned_response([420, 730]),
    )
    games = SteamSource().discover_games(_make_args(no_wishlist=True))
    appids = {g.appid for g in games}
    assert appids == {420, 730}
    assert all(g.source == "owned" for g in games)


@resp_mock.activate
def test_discover_games_owned_empty_library() -> None:
    resp_mock.add(
        resp_mock.GET,
        f"{_STEAM_API}/IPlayerService/GetOwnedGames/v1/",
        json={"response": {}},
    )
    games = SteamSource().discover_games(_make_args(no_wishlist=True))
    assert games == []


# ---------------------------------------------------------------------------
# discover_games — wishlist
# ---------------------------------------------------------------------------


@resp_mock.activate
def test_discover_games_includes_wishlist_by_default() -> None:
    resp_mock.add(
        resp_mock.GET,
        f"{_STEAM_API}/IPlayerService/GetOwnedGames/v1/",
        json=_owned_response([420]),
    )
    resp_mock.add(
        resp_mock.GET,
        f"{_STEAM_API}/IWishlistService/GetWishlist/v1/",
        json=_wishlist_response([730]),
    )
    games = SteamSource().discover_games(_make_args())
    appids = {g.appid for g in games}
    assert 420 in appids
    assert 730 in appids


@resp_mock.activate
def test_discover_games_no_wishlist_flag_skips_wishlist() -> None:
    resp_mock.add(
        resp_mock.GET,
        f"{_STEAM_API}/IPlayerService/GetOwnedGames/v1/",
        json=_owned_response([420]),
    )
    games = SteamSource().discover_games(_make_args(no_wishlist=True))
    # Only one HTTP call should have been made (no wishlist)
    assert len(resp_mock.calls) == 1
    assert all(g.source == "owned" for g in games)


@resp_mock.activate
def test_discover_games_wishlist_source_label() -> None:
    resp_mock.add(
        resp_mock.GET,
        f"{_STEAM_API}/IPlayerService/GetOwnedGames/v1/",
        json=_owned_response([]),
    )
    resp_mock.add(
        resp_mock.GET,
        f"{_STEAM_API}/IWishlistService/GetWishlist/v1/",
        json=_wishlist_response([730]),
    )
    games = SteamSource().discover_games(_make_args())
    wl_games = [g for g in games if g.appid == 730]
    assert wl_games
    assert wl_games[0].source == "wishlist"


@resp_mock.activate
def test_discover_games_wishlist_error_does_not_abort() -> None:
    """A failed wishlist call should not prevent owned games from being returned."""
    resp_mock.add(
        resp_mock.GET,
        f"{_STEAM_API}/IPlayerService/GetOwnedGames/v1/",
        json=_owned_response([420]),
    )
    resp_mock.add(
        resp_mock.GET,
        f"{_STEAM_API}/IWishlistService/GetWishlist/v1/",
        status=403,
    )
    games = SteamSource().discover_games(_make_args())
    assert any(g.appid == 420 for g in games)


# ---------------------------------------------------------------------------
# discover_games — followed games
# ---------------------------------------------------------------------------


@resp_mock.activate
def test_discover_games_followed_not_fetched_by_default() -> None:
    resp_mock.add(
        resp_mock.GET,
        f"{_STEAM_API}/IPlayerService/GetOwnedGames/v1/",
        json=_owned_response([]),
    )
    resp_mock.add(
        resp_mock.GET,
        f"{_STEAM_API}/IWishlistService/GetWishlist/v1/",
        json=_wishlist_response([]),
    )
    SteamSource().discover_games(_make_args(followed=False))
    called_urls = [c.request.url for c in resp_mock.calls if c.request.url]
    assert not any("GetFollowedGames" in url for url in called_urls)


@resp_mock.activate
def test_discover_games_followed_flag_fetches_followed() -> None:
    resp_mock.add(
        resp_mock.GET,
        f"{_STEAM_API}/IPlayerService/GetOwnedGames/v1/",
        json=_owned_response([]),
    )
    resp_mock.add(
        resp_mock.GET,
        f"{_STEAM_API}/IWishlistService/GetWishlist/v1/",
        json=_wishlist_response([]),
    )
    resp_mock.add(
        resp_mock.GET,
        f"{_STEAM_API}/IPlayerService/GetFollowedGames/v1/",
        json=_followed_response([999]),
    )
    games = SteamSource().discover_games(_make_args(followed=True))
    followed_games = [g for g in games if g.appid == 999]
    assert followed_games
    assert followed_games[0].source == "followed"


@resp_mock.activate
def test_discover_games_followed_error_does_not_abort() -> None:
    resp_mock.add(
        resp_mock.GET,
        f"{_STEAM_API}/IPlayerService/GetOwnedGames/v1/",
        json=_owned_response([420]),
    )
    resp_mock.add(
        resp_mock.GET,
        f"{_STEAM_API}/IWishlistService/GetWishlist/v1/",
        json=_wishlist_response([]),
    )
    resp_mock.add(
        resp_mock.GET,
        f"{_STEAM_API}/IPlayerService/GetFollowedGames/v1/",
        status=404,
    )
    games = SteamSource().discover_games(_make_args(followed=True))
    assert any(g.appid == 420 for g in games)


# ---------------------------------------------------------------------------
# discover_games — multi-source result (same appid in owned + wishlist)
# ---------------------------------------------------------------------------


@resp_mock.activate
def test_discover_games_returns_all_entries_including_cross_source_duplicates() -> None:
    """The same appid may appear with both 'owned' and 'wishlist' source labels.

    SteamSource does NOT deduplicate — the caller (CLI + Database) is responsible
    for handling priority. The DB's upsert_game enforces owned > wishlist > followed.
    """
    resp_mock.add(
        resp_mock.GET,
        f"{_STEAM_API}/IPlayerService/GetOwnedGames/v1/",
        json=_owned_response([420]),
    )
    resp_mock.add(
        resp_mock.GET,
        f"{_STEAM_API}/IWishlistService/GetWishlist/v1/",
        json=_wishlist_response([420]),  # same game also in wishlist
    )
    games = SteamSource().discover_games(_make_args())
    owned_entries = [g for g in games if g.appid == 420 and g.source == "owned"]
    wishlist_entries = [g for g in games if g.appid == 420 and g.source == "wishlist"]
    assert owned_entries, "owned entry must be present"
    assert wishlist_entries, "wishlist entry must also be present for DB priority logic"


# ---------------------------------------------------------------------------
# EpicSource — protocol conformance & registry
# ---------------------------------------------------------------------------


def test_epic_source_name() -> None:
    assert EpicSource().name == "epic"


def test_epic_source_is_runtime_checkable() -> None:
    assert isinstance(EpicSource(), GameSource)


def test_get_all_sources_contains_epic_source() -> None:
    sources = get_all_sources()
    assert any(isinstance(s, EpicSource) for s in sources)


# ---------------------------------------------------------------------------
# EpicSource — CLI argument registration
# ---------------------------------------------------------------------------


def test_epic_source_registers_auth_code_argument() -> None:
    parser = argparse.ArgumentParser()
    EpicSource().add_arguments(parser)
    dests = {a.dest for a in parser._actions}
    assert "epic_auth_code" in dests


def test_epic_source_registers_refresh_token_arguments() -> None:
    parser = argparse.ArgumentParser()
    EpicSource().add_arguments(parser)
    dests = {a.dest for a in parser._actions}
    assert "epic_refresh_token" in dests
    assert "epic_account_id" in dests


def test_epic_source_registers_twitch_arguments() -> None:
    parser = argparse.ArgumentParser()
    EpicSource().add_arguments(parser)
    dests = {a.dest for a in parser._actions}
    assert "twitch_client_id" in dests
    assert "twitch_client_secret" in dests


# ---------------------------------------------------------------------------
# EpicSource — is_enabled
# ---------------------------------------------------------------------------


def _epic_args(**kwargs: str | None) -> argparse.Namespace:
    base: dict[str, str | None] = {
        "epic_auth_code": None,
        "epic_refresh_token": None,
        "epic_account_id": None,
        "twitch_client_id": None,
        "twitch_client_secret": None,
        "lang": None,
    }
    base.update(kwargs)
    return argparse.Namespace(**base)


def test_epic_source_enabled_with_auth_code() -> None:
    args = _epic_args(epic_auth_code="someCode")
    assert EpicSource().is_enabled(args) is True


def test_epic_source_enabled_with_refresh_token() -> None:
    args = _epic_args(epic_refresh_token="rt")
    assert EpicSource().is_enabled(args) is True


def test_epic_source_disabled_with_no_credentials() -> None:
    args = _epic_args()
    assert EpicSource().is_enabled(args) is False


def test_epic_source_enabled_with_refresh_token_only() -> None:
    """Refresh token alone is sufficient — account_id is not required."""
    args = _epic_args(epic_refresh_token="rt")  # no account_id
    assert EpicSource().is_enabled(args) is True


# ---------------------------------------------------------------------------
# EpicSource — discover_games (HTTP mocked)
# ---------------------------------------------------------------------------

_EPIC_TOKEN_URL = "https://account-public-service-prod03.ol.epicgames.com/account/api/oauth/token"
_EPIC_LIBRARY_URL = "https://library-service.live.use1a.on.epicgames.com/library/api/public/items"
_STEAM_STORE_SEARCH = "https://store.steampowered.com/api/storesearch/"


def _token_response() -> dict:  # type: ignore[type-arg]
    return {"access_token": "tok_abc", "account_id": "acc_123"}


def _library_response(items: list[dict]) -> dict:  # type: ignore[type-arg]
    return {"records": items, "responseMetadata": {"nextCursor": None}}


@resp_mock.activate
def test_epic_discover_games_returns_epic_source_label() -> None:
    resp_mock.add(resp_mock.POST, _EPIC_TOKEN_URL, json=_token_response())
    resp_mock.add(
        resp_mock.GET,
        _EPIC_LIBRARY_URL,
        json=_library_response([{"catalogItemId": "cat1", "appName": "Fortnite"}]),
    )
    # Store search returns no match → hash-based appid
    resp_mock.add(resp_mock.GET, _STEAM_STORE_SEARCH, json={"total": 0, "items": []})

    games = EpicSource().discover_games(_epic_args(epic_auth_code="code1"))
    assert len(games) == 1
    assert games[0].source == "epic"
    assert games[0].external_id.startswith("epic:")


@resp_mock.activate
def test_epic_discover_games_resolved_appid_used_directly() -> None:
    resp_mock.add(resp_mock.POST, _EPIC_TOKEN_URL, json=_token_response())
    resp_mock.add(
        resp_mock.GET,
        _EPIC_LIBRARY_URL,
        json=_library_response([{"catalogItemId": "cat2", "appName": "Rocket League"}]),
    )
    # Steam Store Search returns an exact match
    resp_mock.add(
        resp_mock.GET,
        _STEAM_STORE_SEARCH,
        json={"total": 1, "items": [{"name": "Rocket League", "id": 252950}]},
    )

    games = EpicSource().discover_games(_epic_args(epic_auth_code="code1"))
    assert len(games) == 1
    assert games[0].appid == 252950


@resp_mock.activate
def test_epic_discover_games_unresolved_gets_hash_appid() -> None:
    resp_mock.add(resp_mock.POST, _EPIC_TOKEN_URL, json=_token_response())
    resp_mock.add(
        resp_mock.GET,
        _EPIC_LIBRARY_URL,
        json=_library_response([{"catalogItemId": "unknownCat", "appName": "SomeExclusiveGame"}]),
    )
    resp_mock.add(resp_mock.GET, _STEAM_STORE_SEARCH, json={"total": 0, "items": []})

    games = EpicSource().discover_games(_epic_args(epic_auth_code="code1"))
    assert len(games) == 1
    assert games[0].appid >= SYNTHETIC_APPID_BASE
    assert games[0].external_id == "epic:unknownCat"


@resp_mock.activate
def test_epic_discover_games_auth_failure_raises() -> None:
    """discover_games must raise (not return []) when authentication fails."""
    resp_mock.add(resp_mock.POST, _EPIC_TOKEN_URL, status=401, json={"error": "invalid_auth"})

    with pytest.raises(requests.HTTPError):
        EpicSource().discover_games(_epic_args(epic_auth_code="bad_code"))


@resp_mock.activate
def test_epic_discover_games_empty_library_returns_empty() -> None:
    resp_mock.add(resp_mock.POST, _EPIC_TOKEN_URL, json=_token_response())
    resp_mock.add(resp_mock.GET, _EPIC_LIBRARY_URL, json=_library_response([]))

    games = EpicSource().discover_games(_epic_args(epic_auth_code="code1"))
    assert games == []


@resp_mock.activate
def test_epic_discover_games_persists_refreshed_token() -> None:
    """discover_games() must update args with the new refresh token."""
    token_resp = {
        "access_token": "tok_new",
        "refresh_token": "rt_rotated",
        "account_id": "acc_456",
    }
    resp_mock.add(resp_mock.POST, _EPIC_TOKEN_URL, json=token_resp)
    resp_mock.add(resp_mock.GET, _EPIC_LIBRARY_URL, json=_library_response([]))

    args = _epic_args(epic_refresh_token="rt_old", epic_account_id="acc_old")
    EpicSource().discover_games(args)

    assert args.epic_refresh_token == "rt_rotated"
    assert args.epic_account_id == "acc_456"


# ===========================================================================
# GogSource
# ===========================================================================

_GOG_TOKEN_URL = "https://auth.gog.com/token"
_GOG_PRODUCTS_URL = "https://embed.gog.com/account/getFilteredProducts"
_STEAM_STORE_SEARCH_URL = "https://store.steampowered.com/api/storesearch/"


def _gog_args(**kwargs: str | None) -> argparse.Namespace:
    base: dict[str, str | None] = {
        "gog_refresh_token": None,
        "twitch_client_id": None,
        "twitch_client_secret": None,
        "lang": None,
    }
    base.update(kwargs)
    return argparse.Namespace(**base)


def _gog_token_resp() -> dict:  # type: ignore[type-arg]
    return {
        "access_token": "gog_access_abc",
        "refresh_token": "gog_refresh_new",
        "expires_in": 3600,
        "token_type": "bearer",
        "user_id": "gog_user_1",
    }


def _gog_products_page(products: list[dict], total_pages: int = 1) -> dict:  # type: ignore[type-arg]
    return {"products": products, "totalPages": total_pages, "page": 1}


# ---------------------------------------------------------------------------
# GogSource — protocol conformance & registry
# ---------------------------------------------------------------------------


def test_gog_source_name() -> None:
    assert GogSource().name == "gog"


def test_gog_source_is_runtime_checkable() -> None:
    assert isinstance(GogSource(), GameSource)


def test_get_all_sources_contains_gog_source() -> None:
    sources = get_all_sources()
    assert any(isinstance(s, GogSource) for s in sources)


# ---------------------------------------------------------------------------
# GogSource — CLI argument registration
# ---------------------------------------------------------------------------


def test_gog_source_registers_refresh_token_argument() -> None:
    parser = argparse.ArgumentParser()
    GogSource().add_arguments(parser)
    dests = {a.dest for a in parser._actions}
    assert "gog_refresh_token" in dests


# ---------------------------------------------------------------------------
# GogSource — is_enabled
# ---------------------------------------------------------------------------


def test_gog_source_disabled_without_token() -> None:
    args = _gog_args()
    assert GogSource().is_enabled(args) is False


def test_gog_source_enabled_with_token() -> None:
    args = _gog_args(gog_refresh_token="some_token")
    assert GogSource().is_enabled(args) is True


def test_gog_source_disabled_with_empty_token() -> None:
    args = _gog_args(gog_refresh_token="")
    assert GogSource().is_enabled(args) is False


# ---------------------------------------------------------------------------
# GogSource — discover_games
# ---------------------------------------------------------------------------


@resp_mock.activate
def test_gog_source_discover_games_returns_gog_source_label() -> None:
    resp_mock.add(resp_mock.GET, _GOG_TOKEN_URL, json=_gog_token_resp())
    resp_mock.add(
        resp_mock.GET,
        _GOG_PRODUCTS_URL,
        json=_gog_products_page([{"id": 1001, "title": "The Witcher 3", "image": ""}]),
    )
    resp_mock.add(resp_mock.GET, _STEAM_STORE_SEARCH_URL, json={"total": 0, "items": []})

    games = GogSource().discover_games(_gog_args(gog_refresh_token="rt"))
    assert len(games) == 1
    assert games[0].source == "gog"
    assert games[0].external_id == "gog:1001"
    assert games[0].name == "The Witcher 3"


@resp_mock.activate
def test_gog_source_resolved_appid_used_directly() -> None:
    resp_mock.add(resp_mock.GET, _GOG_TOKEN_URL, json=_gog_token_resp())
    resp_mock.add(
        resp_mock.GET,
        _GOG_PRODUCTS_URL,
        json=_gog_products_page([{"id": 1002, "title": "Cyberpunk 2077", "image": ""}]),
    )
    resp_mock.add(
        resp_mock.GET,
        _STEAM_STORE_SEARCH_URL,
        json={"total": 1, "items": [{"name": "Cyberpunk 2077", "id": 1091500}]},
    )

    games = GogSource().discover_games(_gog_args(gog_refresh_token="rt"))
    assert games[0].appid == 1091500


@resp_mock.activate
def test_gog_source_synthetic_appid_when_unresolved() -> None:
    resp_mock.add(resp_mock.GET, _GOG_TOKEN_URL, json=_gog_token_resp())
    resp_mock.add(
        resp_mock.GET,
        _GOG_PRODUCTS_URL,
        json=_gog_products_page(
            [{"id": 9999, "title": "Some Exclusive GOG Game", "image": ""}]
        ),
    )
    resp_mock.add(resp_mock.GET, _STEAM_STORE_SEARCH_URL, json={"total": 0, "items": []})

    games = GogSource().discover_games(_gog_args(gog_refresh_token="rt"))
    assert games[0].appid >= SYNTHETIC_APPID_BASE
    assert games[0].external_id == "gog:9999"


@resp_mock.activate
def test_gog_source_persists_refreshed_token() -> None:
    """discover_games() must update args.gog_refresh_token with the new token."""
    resp_mock.add(resp_mock.GET, _GOG_TOKEN_URL, json=_gog_token_resp())
    resp_mock.add(resp_mock.GET, _GOG_PRODUCTS_URL, json=_gog_products_page([]))

    args = _gog_args(gog_refresh_token="rt_old")
    GogSource().discover_games(args)
    assert args.gog_refresh_token == "gog_refresh_new"


@resp_mock.activate
def test_gog_source_auth_failure_raises() -> None:
    resp_mock.add(resp_mock.GET, _GOG_TOKEN_URL, status=401, json={"error": "invalid"})
    with pytest.raises(requests.HTTPError):
        GogSource().discover_games(_gog_args(gog_refresh_token="bad_token"))


@resp_mock.activate
def test_gog_source_empty_library_returns_empty() -> None:
    resp_mock.add(resp_mock.GET, _GOG_TOKEN_URL, json=_gog_token_resp())
    resp_mock.add(resp_mock.GET, _GOG_PRODUCTS_URL, json=_gog_products_page([]))

    games = GogSource().discover_games(_gog_args(gog_refresh_token="rt"))
    assert games == []


# ===========================================================================
# GamePassSource
# ===========================================================================

_GAMEPASS_CATALOG_URL = "https://catalog.gamepass.com/sigls/v2"
_MS_CATALOG_URL = "https://displaycatalog.mp.microsoft.com/v7.0/products"


def _gamepass_args(**kwargs: object) -> argparse.Namespace:
    base: dict[str, object] = {
        "gamepass": False,
        "twitch_client_id": None,
        "twitch_client_secret": None,
        "lang": None,
    }
    base.update(kwargs)
    return argparse.Namespace(**base)


# ---------------------------------------------------------------------------
# GamePassSource — protocol conformance & registry
# ---------------------------------------------------------------------------


def test_gamepass_source_name() -> None:
    assert GamePassSource().name == "gamepass"


def test_gamepass_source_is_runtime_checkable() -> None:
    assert isinstance(GamePassSource(), GameSource)


def test_get_all_sources_contains_gamepass_source() -> None:
    sources = get_all_sources()
    assert any(isinstance(s, GamePassSource) for s in sources)


# ---------------------------------------------------------------------------
# GamePassSource — CLI argument registration
# ---------------------------------------------------------------------------


def test_gamepass_source_registers_game_pass_argument() -> None:
    parser = argparse.ArgumentParser()
    GamePassSource().add_arguments(parser)
    dests = {a.dest for a in parser._actions}
    assert "gamepass" in dests


# ---------------------------------------------------------------------------
# GamePassSource — is_enabled
# ---------------------------------------------------------------------------


def test_gamepass_source_disabled_by_default() -> None:
    assert GamePassSource().is_enabled(_gamepass_args()) is False


def test_gamepass_source_enabled_with_flag() -> None:
    assert GamePassSource().is_enabled(_gamepass_args(gamepass=True)) is True


# ---------------------------------------------------------------------------
# GamePassSource — discover_games
# ---------------------------------------------------------------------------


@resp_mock.activate
def test_gamepass_source_discover_games_returns_gamepass_source_label() -> None:
    resp_mock.add(
        resp_mock.GET,
        _GAMEPASS_CATALOG_URL,
        json=[{"id": "9NBLGGH4NNS1"}, {"id": "9N5TD916686K"}],
    )
    resp_mock.add(
        resp_mock.GET,
        _MS_CATALOG_URL,
        json={
            "Products": [
                {
                    "ProductId": "9NBLGGH4NNS1",
                    "LocalizedProperties": [{"ProductTitle": "Halo Infinite"}],
                },
                {
                    "ProductId": "9N5TD916686K",
                    "LocalizedProperties": [{"ProductTitle": "Forza Horizon 5"}],
                },
            ]
        },
    )
    resp_mock.add(resp_mock.GET, _STEAM_STORE_SEARCH_URL, json={"total": 0, "items": []})
    resp_mock.add(resp_mock.GET, _STEAM_STORE_SEARCH_URL, json={"total": 0, "items": []})

    games = GamePassSource().discover_games(_gamepass_args(gamepass=True))
    assert len(games) == 2
    assert all(g.source == "gamepass" for g in games)
    external_ids = {g.external_id for g in games}
    assert "gamepass:9NBLGGH4NNS1" in external_ids
    assert "gamepass:9N5TD916686K" in external_ids


@resp_mock.activate
def test_gamepass_source_synthetic_appid_when_unresolved() -> None:
    resp_mock.add(
        resp_mock.GET,
        _GAMEPASS_CATALOG_URL,
        json=[{"id": "9NFAKEID0001"}],
    )
    resp_mock.add(
        resp_mock.GET,
        _MS_CATALOG_URL,
        json={
            "Products": [
                {
                    "ProductId": "9NFAKEID0001",
                    "LocalizedProperties": [{"ProductTitle": "Xbox Exclusive"}],
                }
            ]
        },
    )
    resp_mock.add(resp_mock.GET, _STEAM_STORE_SEARCH_URL, json={"total": 0, "items": []})

    games = GamePassSource().discover_games(_gamepass_args(gamepass=True))
    assert games[0].appid >= SYNTHETIC_APPID_BASE
    assert games[0].external_id == "gamepass:9NFAKEID0001"


@resp_mock.activate
def test_gamepass_source_empty_catalog_returns_empty() -> None:
    resp_mock.add(resp_mock.GET, _GAMEPASS_CATALOG_URL, json=[])

    games = GamePassSource().discover_games(_gamepass_args(gamepass=True))
    assert games == []


@resp_mock.activate
def test_epic_discover_games_keeps_token_when_response_omits_it() -> None:
    """If token response lacks refresh_token, args must stay unchanged."""
    resp_mock.add(resp_mock.POST, _EPIC_TOKEN_URL, json=_token_response())
    resp_mock.add(resp_mock.GET, _EPIC_LIBRARY_URL, json=_library_response([]))

    args = _epic_args(epic_refresh_token="rt_original")
    EpicSource().discover_games(args)

    assert args.epic_refresh_token == "rt_original"



_EPIC_CATALOG_BASE = (
    "https://catalog-public-service-prod06.ol.epicgames.com"
    "/catalog/api/shared/namespace"
)


@resp_mock.activate
def test_epic_discover_games_catalog_title_overrides_local() -> None:
    """Catalog API title must take priority over appName / sandboxName."""
    resp_mock.add(resp_mock.POST, _EPIC_TOKEN_URL, json=_token_response())
    resp_mock.add(
        resp_mock.GET,
        _EPIC_LIBRARY_URL,
        json=_library_response([
            {
                "catalogItemId": "cat_abc",
                "appName": "BrilliantRose",          # codename — wrong title
                "namespace": "ns_abc",
                "sandboxName": "BrilliantRose",
            },
        ]),
    )
    # Catalog API returns the real title
    resp_mock.add(
        resp_mock.GET,
        f"{_EPIC_CATALOG_BASE}/ns_abc/bulk/items",
        json={
            "cat_abc": {"id": "cat_abc", "title": "Gone Home"},
        },
    )
    # Steam resolver
    resp_mock.add(resp_mock.GET, _STEAM_STORE_SEARCH, json={"total": 0, "items": []})

    games = EpicSource().discover_games(_epic_args(epic_auth_code="code1"))
    assert len(games) == 1
    assert games[0].name == "Gone Home"


@resp_mock.activate
def test_epic_discover_games_catalog_fallback_to_local() -> None:
    """When Catalog API returns nothing, local extraction is used as fallback."""
    resp_mock.add(resp_mock.POST, _EPIC_TOKEN_URL, json=_token_response())
    resp_mock.add(
        resp_mock.GET,
        _EPIC_LIBRARY_URL,
        json=_library_response([
            {
                "catalogItemId": "cat_xyz",
                "appName": "MyEpicGame",
                "namespace": "ns_xyz",
                "sandboxName": "MyEpicGame",
            },
        ]),
    )
    # Catalog API returns empty (title not found)
    resp_mock.add(
        resp_mock.GET,
        f"{_EPIC_CATALOG_BASE}/ns_xyz/bulk/items",
        json={},
    )
    resp_mock.add(resp_mock.GET, _STEAM_STORE_SEARCH, json={"total": 0, "items": []})

    games = EpicSource().discover_games(_epic_args(epic_auth_code="code1"))
    assert len(games) == 1
    assert games[0].name == "MyEpicGame"


@resp_mock.activate
def test_epic_discover_games_library_failure_raises() -> None:
    """discover_games must raise when the library fetch fails (auth succeeded)."""
    resp_mock.add(resp_mock.POST, _EPIC_TOKEN_URL, json=_token_response())
    resp_mock.add(resp_mock.GET, _EPIC_LIBRARY_URL, status=500)

    with pytest.raises(requests.HTTPError):
        EpicSource().discover_games(_epic_args(epic_auth_code="code1"))


# ---------------------------------------------------------------------------
# source_labels — failed-source protection
# ---------------------------------------------------------------------------


def test_steam_source_has_source_labels() -> None:
    """SteamSource must declare the source values it produces."""
    labels = SteamSource().source_labels
    assert "owned" in labels
    assert "wishlist" in labels
    assert "followed" in labels


def test_epic_source_has_source_labels() -> None:
    """EpicSource must declare 'epic' as its source label."""
    labels = EpicSource().source_labels
    assert "epic" in labels
