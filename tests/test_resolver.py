"""Tests for steam_tracker.resolver — Steam AppID resolution from game names."""
from __future__ import annotations

import pytest
import responses as resp_mock

from steam_tracker.resolver import (
    IGDBResolver,
    SteamStoreResolver,
    _best_match,
    _is_word_contained,
    _is_word_prefix,
    _normalize,
    _shorten_year,
    _strip_edition,
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


# ─── _is_word_prefix ────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("target", "candidate", "expected"),
    [
        ("control", "control ultimate edition", True),
        ("disco elysium", "disco elysium - the final cut", True),
        ("death stranding", "death stranding director's cut", True),
        ("ark", "ark: survival evolved", True),
        ("bus simulator 21", "bus simulator 21 next stop", True),
        # Exact match is also a prefix
        ("hades", "hades", True),
        # NOT a prefix — target is a substring inside a word
        ("control", "steam controller", False),
        # Completely different name
        ("hades", "team fortress 2", False),
        # Target longer than candidate
        ("death stranding director's cut", "death stranding", False),
        # Sequel (digit after separator) — rejected
        ("death stranding", "death stranding 2: on the beach", False),
        ("far cry", "far cry 3", False),
    ],
)
def test_is_word_prefix(target: str, candidate: str, expected: bool) -> None:
    """Verify word-boundary prefix detection."""
    assert _is_word_prefix(target, candidate) is expected


# ─── _best_match prefix fallback ────────────────────────────────────


def test_best_match_prefix_fallback_disco_elysium() -> None:
    """Prefix fallback resolves 'Disco Elysium' to 'Disco Elysium - The Final Cut'."""
    candidates: list[dict[str, object]] = [
        {"id": 632470, "name": "Disco Elysium - The Final Cut"},
        {"id": 1173140, "name": "Disco Elysium - Soundtrack"},
    ]
    match = _best_match("Disco Elysium", candidates)
    assert match is not None
    assert match["id"] == 632470


def test_best_match_prefix_fallback_control() -> None:
    """Prefix fallback resolves 'Control' (ignoring 'Steam Controller')."""
    candidates: list[dict[str, object]] = [
        {"id": 4165870, "name": "Steam Controller"},
        {"id": 870780, "name": "Control Ultimate Edition"},
    ]
    match = _best_match("Control", candidates)
    assert match is not None
    assert match["id"] == 870780


def test_best_match_prefix_fallback_death_stranding() -> None:
    """Prefix fallback picks Director's Cut; sequel (digit suffix) is excluded."""
    candidates: list[dict[str, object]] = [
        {"id": 3280350, "name": "DEATH STRANDING 2: ON THE BEACH"},
        {"id": 1850570, "name": "DEATH STRANDING DIRECTOR'S CUT"},
    ]
    match = _best_match("Death Stranding", candidates)
    assert match is not None
    assert match["id"] == 1850570


def test_best_match_prefix_fallback_bus_simulator() -> None:
    """Prefix fallback resolves 'Bus Simulator 21' to 'Bus Simulator 21 Next Stop'."""
    candidates: list[dict[str, object]] = [
        {"id": 976590, "name": "Bus Simulator 21 Next Stop"},
    ]
    match = _best_match("Bus Simulator 21", candidates)
    assert match is not None
    assert match["id"] == 976590


def test_best_match_prefix_fallback_ark() -> None:
    """Prefix fallback resolves 'Ark' among multiple ARK titles."""
    candidates: list[dict[str, object]] = [
        {"id": 2399830, "name": "ARK: Survival Ascended"},
        {"id": 346110, "name": "ARK: Survival Evolved"},
    ]
    match = _best_match("Ark", candidates)
    assert match is not None
    # Both are prefix matches; higher SequenceMatcher score wins.
    assert match["id"] in (2399830, 346110)


def test_best_match_exact_still_preferred_over_prefix() -> None:
    """An exact SequenceMatcher match >= threshold beats a prefix fallback."""
    candidates: list[dict[str, object]] = [
        {"id": 99, "name": "Hades: Director's Cut"},
        {"id": 100, "name": "Hades"},
    ]
    match = _best_match("Hades", candidates)
    assert match is not None
    assert match["id"] == 100


# ─── SteamStoreResolver with prefix fallback (integration) ──────────


@resp_mock.activate
def test_steam_store_resolver_prefix_match() -> None:
    """Resolver returns appid via prefix fallback for edition-suffixed names."""
    resp_mock.add(
        resp_mock.GET,
        _STORE_SEARCH,
        json={
            "total": 2,
            "items": [
                {"id": 4165870, "name": "Steam Controller"},
                {"id": 870780, "name": "Control Ultimate Edition"},
            ],
        },
    )
    resolver = SteamStoreResolver()
    assert resolver.resolve("Control") == 870780


# ─── _normalize ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Tom Clancy's Ghost Recon® Breakpoint", "tom clancy s ghost recon breakpoint"),
        ("Rise of the Tomb Raider™", "rise of the tomb raider"),
        ("LISA: The Painful", "lisa the painful"),
        ("Shadowrun: Dragonfall - Director's Cut", "shadowrun dragonfall director s cut"),
        ("  Hades  ", "hades"),
    ],
)
def test_normalize(text: str, expected: str) -> None:
    """Normalisation strips symbols and collapses punctuation."""
    assert _normalize(text) == expected


# ─── _is_word_contained ─────────────────────────────────────────────


@pytest.mark.parametrize(
    ("target", "candidate", "expected"),
    [
        ("ghost recon breakpoint", "tom clancy s ghost recon breakpoint", True),
        ("dungeon of naheulbeuk", "the dungeon of naheulbeuk the amulet of chaos", True),
        ("shadowrun dragonfall", "shadowrun dragonfall director s cut", True),
        # Exact equality
        ("hades", "hades", True),
        # Partial word mismatch
        ("ghost recon", "tom clancy s ghost reconquista", False),
        # Fully different
        ("hades", "celeste", False),
    ],
)
def test_is_word_contained(target: str, candidate: str, expected: bool) -> None:
    """Word-boundary containment detection."""
    assert _is_word_contained(target, candidate) is expected


# ─── _best_match containment fallback ────────────────────────────────


def test_best_match_containment_ghost_recon() -> None:
    """Containment fallback resolves 'Ghost Recon Breakpoint'."""
    candidates: list[dict[str, object]] = [
        {"id": 2231380, "name": "Tom Clancy's Ghost Recon\u00ae Breakpoint"},
    ]
    match = _best_match("Ghost Recon Breakpoint", candidates)
    assert match is not None
    assert match["id"] == 2231380


def test_best_match_containment_dungeon_naheulbeuk() -> None:
    """Containment fallback resolves 'Dungeon Of Naheulbeuk'."""
    candidates: list[dict[str, object]] = [
        {"id": 970830, "name": "The Dungeon Of Naheulbeuk: The Amulet Of Chaos"},
    ]
    match = _best_match("Dungeon Of Naheulbeuk", candidates)
    assert match is not None
    assert match["id"] == 970830


def test_best_match_containment_shadowrun() -> None:
    """Containment fallback resolves 'Shadowrun Dragonfall'."""
    candidates: list[dict[str, object]] = [
        {"id": 300550, "name": "Shadowrun: Dragonfall - Director's Cut"},
    ]
    match = _best_match("Shadowrun Dragonfall", candidates)
    assert match is not None
    assert match["id"] == 300550


def test_best_match_exact_still_preferred_over_containment() -> None:
    """Exact SequenceMatcher match beats containment fallback."""
    candidates: list[dict[str, object]] = [
        {"id": 1, "name": "The Dungeon Of Naheulbeuk: The Amulet Of Chaos"},
        {"id": 2, "name": "Dungeon Of Naheulbeuk"},
    ]
    match = _best_match("Dungeon Of Naheulbeuk", candidates)
    assert match is not None
    assert match["id"] == 2


# ─── _strip_edition ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("LISA: The Joyful - Definitive Edition", "LISA: The Joyful"),
        ("Dragon Age: Inquisition - Game of the Year Edition", "Dragon Age: Inquisition"),
        ("Rise of the Tomb Raider: 20 Year Celebration", "Rise of the Tomb Raider"),
        ("Hades - GOTY Edition", "Hades"),
        ("Control - Ultimate Edition", "Control"),
        ("Baldur's Gate - Enhanced Edition", "Baldur's Gate"),
        ("Game - Directors Cut", "Game"),
        # No edition suffix → None.
        ("Hades", None),
        ("Farming Simulator 2022", None),
    ],
)
def test_strip_edition(name: str, expected: str | None) -> None:
    """Edition / subtitle suffix stripping."""
    assert _strip_edition(name) == expected


# ─── _shorten_year ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Farming Simulator 2022", "Farming Simulator 22"),
        ("F1 2019", "F1 19"),
        # Not a 20xx year → unchanged.
        ("Hades", None),
        ("Bus Simulator 21", None),
    ],
)
def test_shorten_year(name: str, expected: str | None) -> None:
    """4-digit year shortening (20xx → xx)."""
    assert _shorten_year(name) == expected


# ─── SteamStoreResolver retry strategies (integration) ───────────────


@resp_mock.activate
def test_steam_store_resolver_retries_with_stripped_edition() -> None:
    """When first search returns nothing, retry with edition suffix stripped."""
    # First search: "LISA: The Joyful - Definitive Edition" → no results
    resp_mock.add(
        resp_mock.GET,
        _STORE_SEARCH,
        json={"total": 0, "items": []},
    )
    # Retry search: "LISA: The Joyful" → found
    resp_mock.add(
        resp_mock.GET,
        _STORE_SEARCH,
        json={
            "total": 1,
            "items": [{"id": 379310, "name": "LISA the Joyful"}],
        },
    )
    resolver = SteamStoreResolver()
    assert resolver.resolve("LISA: The Joyful - Definitive Edition") == 379310


@resp_mock.activate
def test_steam_store_resolver_retries_with_shortened_year() -> None:
    """When both original and stripped fail, retry with 2-digit year."""
    # First search: "Farming Simulator 2022" → no results
    resp_mock.add(
        resp_mock.GET,
        _STORE_SEARCH,
        json={"total": 0, "items": []},
    )
    # No edition suffix to strip → goes directly to year retry.
    # Year retry: "Farming Simulator 22" → found
    resp_mock.add(
        resp_mock.GET,
        _STORE_SEARCH,
        json={
            "total": 1,
            "items": [{"id": 1248130, "name": "Farming Simulator 22"}],
        },
    )
    resolver = SteamStoreResolver()
    assert resolver.resolve("Farming Simulator 2022") == 1248130


@resp_mock.activate
def test_steam_store_resolver_containment_match() -> None:
    """Resolver returns appid via containment fallback."""
    resp_mock.add(
        resp_mock.GET,
        _STORE_SEARCH,
        json={
            "total": 1,
            "items": [
                {"id": 2231380, "name": "Tom Clancy's Ghost Recon\u00ae Breakpoint"},
            ],
        },
    )
    resolver = SteamStoreResolver()
    assert resolver.resolve("Ghost Recon Breakpoint") == 2231380
