"""Tests for steam_tracker.db."""
from __future__ import annotations

from steam_tracker.db import Database, infer_status
from steam_tracker.models import AppDetails, GameStatus, NewsItem, OwnedGame


def test_upsert_and_retrieve_game(db: Database, sample_game: OwnedGame) -> None:
    db.upsert_game(sample_game)
    records = db.get_all_game_records()
    assert len(records) == 1
    assert records[0].game.appid == sample_game.appid
    assert records[0].game.name == sample_game.name


def test_upsert_game_updates_playtime(db: Database, sample_game: OwnedGame) -> None:
    db.upsert_game(sample_game)
    updated = sample_game.model_copy(update={"playtime_forever": 9999})
    db.upsert_game(updated)
    records = db.get_all_game_records()
    assert records[0].game.playtime_forever == 9999


def test_upsert_game_stores_new_fields(db: Database, sample_game: OwnedGame) -> None:
    db.upsert_game(sample_game)
    g = db.get_all_game_records()[0].game
    assert g.playtime_2weeks == sample_game.playtime_2weeks
    assert g.rtime_last_played == sample_game.rtime_last_played


def test_upsert_app_details(
    db: Database, sample_game: OwnedGame, sample_details: AppDetails
) -> None:
    db.upsert_game(sample_game)
    db.upsert_app_details(sample_details)
    assert 420 in db.get_cached_appids()
    records = db.get_all_game_records()
    assert records[0].details is not None
    assert records[0].details.release_date_str == sample_details.release_date_str


def test_upsert_app_details_json_list_roundtrip(
    db: Database, sample_game: OwnedGame, sample_details: AppDetails
) -> None:
    db.upsert_game(sample_game)
    db.upsert_app_details(sample_details)
    det = db.get_all_game_records()[0].details
    assert det is not None
    assert det.developers == ["Valve"]
    assert det.genres == ["Action", "Shooter"]
    assert det.categories == ["Single-player", "Steam Achievements"]
    assert det.publishers == ["Valve"]


def test_upsert_app_details_scalar_new_fields(
    db: Database, sample_game: OwnedGame, sample_details: AppDetails
) -> None:
    db.upsert_game(sample_game)
    db.upsert_app_details(sample_details)
    det = db.get_all_game_records()[0].details
    assert det is not None
    assert det.app_type == "game"
    assert det.is_free is False
    assert det.price_initial == 999
    assert det.price_currency == "EUR"
    assert det.platform_windows is True
    assert det.platform_linux is True
    assert det.metacritic_score == 96
    assert det.achievement_count == 42
    assert det.recommendation_count == 300000


def test_upsert_news(
    db: Database, sample_game: OwnedGame, sample_news: list[NewsItem]
) -> None:
    db.upsert_game(sample_game)
    db.upsert_news(sample_game.appid, sample_news)
    records = db.get_all_game_records()
    assert len(records[0].news) == 1
    assert records[0].news[0].title == "Update 1.0"


def test_upsert_news_stores_new_fields(
    db: Database, sample_game: OwnedGame, sample_news: list[NewsItem]
) -> None:
    db.upsert_game(sample_game)
    db.upsert_news(sample_game.appid, sample_news)
    item = db.get_all_game_records()[0].news[0]
    assert item.gid == "123456789"
    assert item.author == "Valve"
    assert item.feedlabel == "Community Announcements"
    assert item.tags == ["patchnotes", "valve"]


def test_upsert_news_deduplicates_by_url(
    db: Database, sample_game: OwnedGame, sample_news: list[NewsItem]
) -> None:
    db.upsert_game(sample_game)
    db.upsert_news(sample_game.appid, sample_news)
    db.upsert_news(sample_game.appid, sample_news)  # same batch again
    records = db.get_all_game_records()
    assert len(records[0].news) == 1


def test_get_cached_appids_empty_before_details(
    db: Database, sample_game: OwnedGame
) -> None:
    db.upsert_game(sample_game)
    assert db.get_cached_appids() == set()


def test_get_cached_appids_after_failed_fetch(
    db: Database, sample_game: OwnedGame
) -> None:
    """A game whose API call returned None should still be skipped after mark_fetched."""
    db.upsert_game(sample_game)
    db.mark_fetched({sample_game.appid}, details=True)
    assert sample_game.appid in db.get_cached_appids()


def test_get_stale_news_appids_respects_news_fetched_at(
    db: Database, sample_game: OwnedGame
) -> None:
    """A game with 0 news but a recent news_fetched_at should NOT be considered stale."""
    db.upsert_game(sample_game)
    db.mark_fetched({sample_game.appid}, news=True)
    stale = db.get_stale_news_appids(max_age_seconds=3600)
    assert sample_game.appid not in stale


def test_mark_fetched_details_only(db: Database, sample_game: OwnedGame) -> None:
    db.upsert_game(sample_game)
    db.mark_fetched({sample_game.appid}, details=True)
    # details_fetched_at set but news_fetched_at still NULL → still stale for news
    stale = db.get_stale_news_appids(max_age_seconds=3600)
    assert sample_game.appid in stale


def test_infer_status_released(sample_details: AppDetails) -> None:
    status = infer_status(sample_details)
    assert isinstance(status, GameStatus)
    assert status.badge == "released"


def test_infer_status_early_access(db: Database, sample_game: OwnedGame) -> None:
    db.upsert_game(sample_game)
    ea = AppDetails(appid=420, early_access=True, coming_soon=False)
    db.upsert_app_details(ea)
    assert db.get_all_game_records()[0].status.badge == "earlyaccess"


def test_infer_status_coming_soon(db: Database, sample_game: OwnedGame) -> None:
    db.upsert_game(sample_game)
    cs = AppDetails(appid=420, early_access=False, coming_soon=True)
    db.upsert_app_details(cs)
    assert db.get_all_game_records()[0].status.badge == "unreleased"


def test_infer_status_unknown_without_details(
    db: Database, sample_game: OwnedGame
) -> None:
    db.upsert_game(sample_game)
    assert db.get_all_game_records()[0].status.badge == "unknown"


def test_games_sorted_case_insensitively(db: Database) -> None:
    for name, appid in [("Zelda", 1), ("alpha", 2), ("Beta", 3)]:
        db.upsert_game(OwnedGame(appid=appid, name=name))
    names = [r.game.name for r in db.get_all_game_records()]
    assert names == sorted(names, key=str.lower)


# ─── appid_mappings ──────────────────────────────────────────────────


def test_upsert_appid_mapping_insert(db: Database) -> None:
    db.upsert_appid_mapping("epic", "abc123", "Hades", 1145360)
    assert db.get_appid_mapping("epic", "abc123") == 1145360


def test_upsert_appid_mapping_update(db: Database) -> None:
    db.upsert_appid_mapping("epic", "abc123", "Hades", None)
    assert db.get_appid_mapping("epic", "abc123") is None
    db.upsert_appid_mapping("epic", "abc123", "Hades", 1145360)
    assert db.get_appid_mapping("epic", "abc123") == 1145360


def test_get_appid_mapping_not_found(db: Database) -> None:
    assert db.get_appid_mapping("epic", "nonexistent") is None


def test_manual_mapping_preserved(db: Database) -> None:
    """A manual mapping must not be overwritten by automatic resolution."""
    db.upsert_appid_mapping("epic", "abc123", "Hades", 999, manual=True)
    # Auto-resolve tries to overwrite with a different appid
    db.upsert_appid_mapping("epic", "abc123", "Hades", 1145360, manual=False)
    assert db.get_appid_mapping("epic", "abc123") == 999


def test_manual_mapping_overwritten_by_manual(db: Database) -> None:
    """A manual mapping CAN be overwritten by another manual mapping."""
    db.upsert_appid_mapping("epic", "abc123", "Hades", 999, manual=True)
    db.upsert_appid_mapping("epic", "abc123", "Hades", 1145360, manual=True)
    assert db.get_appid_mapping("epic", "abc123") == 1145360


# ─── external_id ─────────────────────────────────────────────────────


def test_owned_game_external_id_default() -> None:
    game = OwnedGame(appid=1, name="Test")
    assert game.external_id == ""


def test_upsert_game_stores_external_id(db: Database) -> None:
    game = OwnedGame(appid=1, name="Hades", source="epic", external_id="epic:abc123")
    db.upsert_game(game)
    rec = db.get_all_game_records()[0]
    assert rec.game.external_id == "epic:abc123"
    assert rec.game.source == "epic"


def test_upsert_game_external_id_preserved_on_update(db: Database) -> None:
    """An update with empty external_id must NOT erase an existing one."""
    game = OwnedGame(appid=1, name="Hades", source="epic", external_id="epic:abc123")
    db.upsert_game(game)
    update = OwnedGame(appid=1, name="Hades", source="owned")
    db.upsert_game(update)
    rec = db.get_all_game_records()[0]
    assert rec.game.external_id == "epic:abc123"


def test_upsert_game_epic_source_priority(db: Database) -> None:
    """Epic source has same priority as owned — whichever is inserted first wins."""
    db.upsert_game(OwnedGame(appid=1, name="Hades", source="epic"))
    db.upsert_game(OwnedGame(appid=1, name="Hades", source="wishlist"))
    assert db.get_all_game_records()[0].game.source == "epic"

    db.upsert_game(OwnedGame(appid=2, name="Celeste", source="wishlist"))
    db.upsert_game(OwnedGame(appid=2, name="Celeste", source="epic"))
    assert db.get_all_game_records()[0].game.source == "epic"


def test_upsert_game_epic_vs_owned_first_wins(db: Database) -> None:
    """When epic and owned collide, the first-inserted source is preserved."""
    # epic first → stays epic even after owned upsert
    db.upsert_game(OwnedGame(appid=10, name="Hades", source="epic"))
    db.upsert_game(OwnedGame(appid=10, name="Hades", source="owned"))
    assert db.get_all_game_records()[0].game.source == "epic"

    # owned first → stays owned even after epic upsert
    db.upsert_game(OwnedGame(appid=11, name="Celeste", source="owned"))
    db.upsert_game(OwnedGame(appid=11, name="Celeste", source="epic"))
    records = {r.game.appid: r.game.source for r in db.get_all_game_records()}
    assert records[11] == "owned"

