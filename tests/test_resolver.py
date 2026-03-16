"""Tests for steam_tracker.resolver — Steam AppID resolution from game names."""
from __future__ import annotations

import responses as resp_mock

from steam_tracker.resolver import (
    IGDBResolver,
    SteamStoreResolver,
    resolve_steam_appid,
)

_STORE_SEARCH = "https://store.steampowered.com/api/storesearch/"
_TWITCH_TOKEN = "https://id.twitch.tv/oauth2/token"
_IGDB_GAMES = "https://api.igdb.com/v4/games"
_IGDB_EXTERNAL = "https://api.igdb.com/v4/external_games"


# ─── SteamStoreResolver ─────────────────────────────────────────────


@resp_mock.activate
def test_steam_store_resolver_exact_match() -> None:
    """Exact name match returns the appid."""
    resp_mock.add(
        resp_mock.GET,
        _STORE_SEARCH,
        json={
            "total": 1,
            "items": [{"id": 1145360, "name": "Hades"}],
        },
    )
    resolver = SteamStoreResolver()
    assert resolver.resolve("Hades") == 1145360


@resp_mock.activate
def test_steam_store_resolver_fuzzy_match() -> None:
    """Close enough name (ratio > 0.8) still matches."""
    resp_mock.add(
        resp_mock.GET,
        _STORE_SEARCH,
        json={
            "total": 2,
            "items": [
                {"id": 99999, "name": "Hades: The Board Game"},
                {"id": 1145360, "name": "Hades"},
            ],
        },
    )
    resolver = SteamStoreResolver()
    assert resolver.resolve("Hades") == 1145360


@resp_mock.activate
def test_steam_store_resolver_no_match() -> None:
    """No items → None."""
    resp_mock.add(
        resp_mock.GET,
        _STORE_SEARCH,
        json={"total": 0, "items": []},
    )
    resolver = SteamStoreResolver()
    assert resolver.resolve("JeuInexistant12345") is None


@resp_mock.activate
def test_steam_store_resolver_low_similarity() -> None:
    """All results below similarity threshold → None."""
    resp_mock.add(
        resp_mock.GET,
        _STORE_SEARCH,
        json={
            "total": 1,
            "items": [{"id": 440, "name": "Team Fortress 2"}],
        },
    )
    resolver = SteamStoreResolver()
    assert resolver.resolve("Hades") is None


@resp_mock.activate
def test_steam_store_resolver_http_error() -> None:
    """HTTP error → None (graceful)."""
    resp_mock.add(resp_mock.GET, _STORE_SEARCH, status=500)
    resolver = SteamStoreResolver()
    assert resolver.resolve("Hades") is None


# ─── IGDBResolver ────────────────────────────────────────────────────


@resp_mock.activate
def test_igdb_resolver_found() -> None:
    """IGDB search → external_games with category=1 (Steam) → appid."""
    # Twitch OAuth token
    resp_mock.add(
        resp_mock.POST,
        _TWITCH_TOKEN,
        json={"access_token": "tok123", "expires_in": 3600, "token_type": "bearer"},
    )
    # IGDB game search
    resp_mock.add(
        resp_mock.POST,
        _IGDB_GAMES,
        json=[{"id": 113112, "name": "Hades"}],
    )
    # IGDB external_games for the found game
    resp_mock.add(
        resp_mock.POST,
        _IGDB_EXTERNAL,
        json=[{"game": 113112, "uid": "1145360", "category": 1}],
    )
    resolver = IGDBResolver(
        twitch_client_id="fake_client",
        twitch_client_secret="fake_secret",
    )
    assert resolver.resolve("Hades") == 1145360


@resp_mock.activate
def test_igdb_resolver_no_steam_external() -> None:
    """IGDB finds the game but no Steam external_game → None."""
    resp_mock.add(
        resp_mock.POST,
        _TWITCH_TOKEN,
        json={"access_token": "tok123", "expires_in": 3600, "token_type": "bearer"},
    )
    resp_mock.add(
        resp_mock.POST,
        _IGDB_GAMES,
        json=[{"id": 999, "name": "Epic Exclusive Game"}],
    )
    resp_mock.add(
        resp_mock.POST,
        _IGDB_EXTERNAL,
        json=[],
    )
    resolver = IGDBResolver(
        twitch_client_id="fake_client",
        twitch_client_secret="fake_secret",
    )
    assert resolver.resolve("Epic Exclusive Game") is None


@resp_mock.activate
def test_igdb_resolver_no_game_found() -> None:
    """IGDB search returns empty results → None."""
    resp_mock.add(
        resp_mock.POST,
        _TWITCH_TOKEN,
        json={"access_token": "tok123", "expires_in": 3600, "token_type": "bearer"},
    )
    resp_mock.add(resp_mock.POST, _IGDB_GAMES, json=[])
    resolver = IGDBResolver(
        twitch_client_id="fake_client",
        twitch_client_secret="fake_secret",
    )
    assert resolver.resolve("JeuInexistant12345") is None


def test_igdb_resolver_no_credentials() -> None:
    """No Twitch credentials → resolve returns None immediately."""
    resolver = IGDBResolver(twitch_client_id="", twitch_client_secret="")
    assert resolver.resolve("Hades") is None


@resp_mock.activate
def test_igdb_resolver_token_error() -> None:
    """Twitch OAuth failure → None (graceful)."""
    resp_mock.add(resp_mock.POST, _TWITCH_TOKEN, status=401)
    resolver = IGDBResolver(
        twitch_client_id="fake_client",
        twitch_client_secret="fake_secret",
    )
    assert resolver.resolve("Hades") is None


@resp_mock.activate
def test_igdb_resolver_picks_best_match() -> None:
    """When IGDB returns multiple games, pick the one with best name similarity."""
    resp_mock.add(
        resp_mock.POST,
        _TWITCH_TOKEN,
        json={"access_token": "tok", "expires_in": 3600, "token_type": "bearer"},
    )
    resp_mock.add(
        resp_mock.POST,
        _IGDB_GAMES,
        json=[
            {"id": 1, "name": "Hades II"},
            {"id": 2, "name": "Hades"},
        ],
    )
    resp_mock.add(
        resp_mock.POST,
        _IGDB_EXTERNAL,
        json=[{"game": 2, "uid": "1145360", "category": 1}],
    )
    resolver = IGDBResolver(
        twitch_client_id="fake_client",
        twitch_client_secret="fake_secret",
    )
    assert resolver.resolve("Hades") == 1145360


# ─── resolve_steam_appid chain ───────────────────────────────────────


@resp_mock.activate
def test_resolve_chain_first_wins() -> None:
    """First resolver to return a result wins."""
    resp_mock.add(
        resp_mock.GET,
        _STORE_SEARCH,
        json={"total": 1, "items": [{"id": 1145360, "name": "Hades"}]},
    )
    resolvers = [SteamStoreResolver()]
    assert resolve_steam_appid("Hades", resolvers) == 1145360


@resp_mock.activate
def test_resolve_chain_fallback() -> None:
    """If first resolver fails, second one is tried."""
    # Steam store returns nothing
    resp_mock.add(
        resp_mock.GET,
        _STORE_SEARCH,
        json={"total": 0, "items": []},
    )
    # IGDB succeeds
    resp_mock.add(
        resp_mock.POST,
        _TWITCH_TOKEN,
        json={"access_token": "tok", "expires_in": 3600, "token_type": "bearer"},
    )
    resp_mock.add(
        resp_mock.POST,
        _IGDB_GAMES,
        json=[{"id": 113112, "name": "Hades"}],
    )
    resp_mock.add(
        resp_mock.POST,
        _IGDB_EXTERNAL,
        json=[{"game": 113112, "uid": "1145360", "category": 1}],
    )
    resolvers = [
        SteamStoreResolver(),
        IGDBResolver(twitch_client_id="fake", twitch_client_secret="fake"),
    ]
    assert resolve_steam_appid("Hades", resolvers) == 1145360


@resp_mock.activate
def test_resolve_chain_all_fail() -> None:
    """All resolvers fail → None."""
    resp_mock.add(resp_mock.GET, _STORE_SEARCH, json={"total": 0, "items": []})
    resolvers = [SteamStoreResolver()]
    assert resolve_steam_appid("NoSuchGame", resolvers) is None
