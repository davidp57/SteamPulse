"""Tests for steam_tracker.cli helpers."""
from __future__ import annotations

from steam_tracker import __version__
from steam_tracker.cli import _build_enrichment_queue
from steam_tracker.models import SYNTHETIC_APPID_BASE, OwnedGame

# ---------------------------------------------------------------------------
# _build_enrichment_queue
# ---------------------------------------------------------------------------


def _steam(appid: int, **kwargs: object) -> OwnedGame:
    """Build a plain Steam-owned game."""
    return OwnedGame(appid=appid, name=f"Steam:{appid}", **kwargs)  # type: ignore[arg-type]


def _epic_resolved(appid: int, catalog_id: str = "catXYZ") -> OwnedGame:
    """Build an Epic game that was resolved to a real Steam AppID."""
    return OwnedGame(
        appid=appid,
        name=f"Epic resolved:{appid}",
        source="epic",
        external_id=f"epic:{catalog_id}",
    )


def _epic_unresolved(catalog_id: str = "unknownCat") -> OwnedGame:
    """Build an unresolved Epic game with a synthetic hash-based appid."""
    # Mimic _hash_appid(): any value >= SYNTHETIC_APPID_BASE is fine for tests.
    synthetic = SYNTHETIC_APPID_BASE + 42
    return OwnedGame(
        appid=synthetic,
        name="Epic unresolved",
        source="epic",
        external_id=f"epic:{catalog_id}",
    )


def test_plain_steam_games_are_included() -> None:
    games = [_steam(1), _steam(2)]
    result = _build_enrichment_queue(games)
    assert [g.appid for g in result] == [1, 2]


def test_resolved_epic_game_is_included() -> None:
    """An Epic game whose appid was resolved to a real Steam AppID must be enriched."""
    epic = _epic_resolved(appid=252950, catalog_id="rocketleague")
    result = _build_enrichment_queue([epic])
    assert len(result) == 1
    assert result[0].appid == 252950


def test_unresolved_epic_game_is_excluded() -> None:
    """An unresolved Epic game (synthetic appid) must NOT be sent to the Steam Store API."""
    epic = _epic_unresolved()
    result = _build_enrichment_queue([epic])
    assert result == []


def test_mixed_list_filters_correctly() -> None:
    steam = _steam(570)
    resolved = _epic_resolved(appid=252950)
    unresolved = _epic_unresolved()
    result = _build_enrichment_queue([steam, resolved, unresolved])
    appids = [g.appid for g in result]
    assert 570 in appids
    assert 252950 in appids
    assert unresolved.appid not in appids


def test_deduplication_keeps_first_occurrence() -> None:
    """If the same appid appears twice (owned + resolved Epic), only keep the first."""
    owned = _steam(252950)
    epic = _epic_resolved(appid=252950)
    result = _build_enrichment_queue([owned, epic])
    assert len(result) == 1
    assert result[0].source == "owned"


def test_empty_input_returns_empty() -> None:
    assert _build_enrichment_queue([]) == []


def test_all_unresolved_returns_empty() -> None:
    games = [_epic_unresolved(f"cat{i}") for i in range(5)]
    # give each a distinct synthetic appid to avoid dedup collisions
    for i, g in enumerate(games):
        object.__setattr__(g, "appid", SYNTHETIC_APPID_BASE + i)
    assert _build_enrichment_queue(games) == []


def test_synthetic_appid_boundary_excluded() -> None:
    """appid == SYNTHETIC_APPID_BASE must be excluded (boundary value)."""
    boundary = OwnedGame(appid=SYNTHETIC_APPID_BASE, name="Boundary", source="epic")
    result = _build_enrichment_queue([boundary])
    assert result == []


def test_appid_just_below_boundary_included() -> None:
    """appid == SYNTHETIC_APPID_BASE - 1 is a valid Steam AppID and must be included."""
    edge = OwnedGame(appid=SYNTHETIC_APPID_BASE - 1, name="EdgeSteam")
    result = _build_enrichment_queue([edge])
    assert len(result) == 1
    assert result[0].appid == SYNTHETIC_APPID_BASE - 1


# ---------------------------------------------------------------------------
# __version__
# ---------------------------------------------------------------------------


def test_version_is_string() -> None:
    """__version__ must be a non-empty string."""
    assert isinstance(__version__, str)
    assert len(__version__) > 0


def test_version_matches_semver() -> None:
    """__version__ must look like a semver (X.Y.Z)."""
    parts = __version__.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)
