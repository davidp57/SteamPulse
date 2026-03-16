"""Tests for steam_tracker.sources (GameSource protocol + SteamSource plugin)."""
from __future__ import annotations

import argparse

import responses as resp_mock

from steam_tracker.models import OwnedGame
from steam_tracker.sources import GameSource, get_all_sources
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
    called_urls = [c.request.url for c in resp_mock.calls]
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
