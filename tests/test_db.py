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


def test_upsert_app_details_first_insert_returns_no_changes(
    db: Database, sample_game: OwnedGame, sample_details: AppDetails
) -> None:
    """First insert must not return field changes (avoids spurious alerts)."""
    db.upsert_game(sample_game)
    changes = db.upsert_app_details(sample_details)
    assert changes == []


def test_upsert_app_details_update_returns_changes(
    db: Database, sample_game: OwnedGame
) -> None:
    """Subsequent updates must return only the changed fields."""
    db.upsert_game(OwnedGame(appid=420, name="Half-Life 2"))
    db.upsert_app_details(AppDetails(appid=420, buildid=1000))
    changes = db.upsert_app_details(AppDetails(appid=420, buildid=1001))
    buildid_changes = [c for c in changes if c.field_name == "buildid"]
    assert len(buildid_changes) == 1
    assert buildid_changes[0].old_value == "1000"
    assert buildid_changes[0].new_value == "1001"


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


def test_upsert_game_owned_beats_epic(db: Database) -> None:
    """owned always wins over epic, regardless of insertion order."""
    # epic first → owned overwrites
    db.upsert_game(OwnedGame(appid=10, name="Hades", source="epic"))
    db.upsert_game(OwnedGame(appid=10, name="Hades", source="owned"))
    assert db.get_all_game_records()[0].game.source == "owned"

    # owned first → stays owned
    db.upsert_game(OwnedGame(appid=11, name="Celeste", source="owned"))
    db.upsert_game(OwnedGame(appid=11, name="Celeste", source="epic"))
    records = {r.game.appid: r.game.source for r in db.get_all_game_records()}
    assert records[11] == "owned"


# ─── run_cleanup ──────────────────────────────────────────────────────


def test_cleanup_removes_epic_live_games(db: Database) -> None:
    """Games named 'Live' with source='epic' must be deleted by cleanup."""
    db.upsert_game(OwnedGame(appid=2_000_000_001, name="Live", source="epic",
                              external_id="epic:cat1"))
    db.upsert_game(OwnedGame(appid=2_000_000_002, name="Live", source="epic",
                              external_id="epic:cat2"))
    assert len(db.get_all_game_records()) == 2

    cleaned = db.run_cleanup()
    assert cleaned == 2
    assert db.get_all_game_records() == []


def test_cleanup_removes_matching_appid_mappings(db: Database) -> None:
    """Cleanup must also delete appid_mappings for 'Live' Epic entries."""
    db.upsert_game(OwnedGame(appid=2_000_000_001, name="Live", source="epic",
                              external_id="epic:cat1"))
    db.upsert_appid_mapping("epic", "epic:cat1", "Live", None)

    # The mapping row exists (even though steam_appid is NULL)
    with db._connect() as con:
        count = con.execute(
            "SELECT COUNT(*) FROM appid_mappings"
            " WHERE external_source = 'epic' AND external_id = 'epic:cat1'",
        ).fetchone()[0]
    assert count == 1

    db.run_cleanup()

    # After cleanup, the mapping row itself must be gone
    with db._connect() as con:
        count = con.execute(
            "SELECT COUNT(*) FROM appid_mappings"
            " WHERE external_source = 'epic' AND external_id = 'epic:cat1'",
        ).fetchone()[0]
    assert count == 0
    assert db.get_all_game_records() == []


def test_cleanup_preserves_non_live_epic_games(db: Database) -> None:
    """Epic games with a real title must NOT be deleted."""
    db.upsert_game(OwnedGame(appid=2_000_000_001, name="Hades", source="epic",
                              external_id="epic:cat_hades"))
    db.upsert_game(OwnedGame(appid=2_000_000_002, name="Live", source="epic",
                              external_id="epic:cat_bad"))

    cleaned = db.run_cleanup()
    assert cleaned == 1
    records = db.get_all_game_records()
    assert len(records) == 1
    assert records[0].game.name == "Hades"


def test_cleanup_preserves_non_epic_games(db: Database) -> None:
    """Steam games named 'Live' (hypothetical) must NOT be touched."""
    db.upsert_game(OwnedGame(appid=999, name="Live", source="owned"))

    cleaned = db.run_cleanup()
    assert cleaned == 0
    assert len(db.get_all_game_records()) == 1


def test_cleanup_removes_epic_hex_id_games(db: Database) -> None:
    """Games with hex-ID names (24+ lowercase hex chars) and source='epic' must be deleted."""
    db.upsert_game(OwnedGame(appid=2_000_000_010, name="0074f9a408204f1f869d9d6f26b99521",
                              source="epic", external_id="epic:hex1"))
    db.upsert_game(OwnedGame(appid=2_000_000_011, name="002b000085aeb49b1a3f3c42e3f918f2f",
                              source="epic", external_id="epic:hex2"))
    assert len(db.get_all_game_records()) == 2

    cleaned = db.run_cleanup()
    assert cleaned == 2
    assert db.get_all_game_records() == []


def test_cleanup_hex_id_removes_appid_mappings(db: Database) -> None:
    """Cleanup must also delete appid_mappings for hex-ID Epic entries."""
    db.upsert_game(OwnedGame(appid=2_000_000_010, name="0074f9a408204f1f869d9d6f26b99521",
                              source="epic", external_id="epic:hex1"))
    db.upsert_appid_mapping("epic", "epic:hex1", "0074f9a408204f1f869d9d6f26b99521", None)

    db.run_cleanup()

    with db._connect() as con:
        count = con.execute(
            "SELECT COUNT(*) FROM appid_mappings"
            " WHERE external_source = 'epic' AND external_id = 'epic:hex1'",
        ).fetchone()[0]
    assert count == 0
    assert db.get_all_game_records() == []


def test_cleanup_preserves_non_hex_epic_games(db: Database) -> None:
    """Epic games with a real title must NOT be deleted by hex-ID rule."""
    db.upsert_game(OwnedGame(appid=2_000_000_010, name="Hades", source="epic",
                              external_id="epic:cat_hades"))
    db.upsert_game(OwnedGame(appid=2_000_000_011, name="0074f9a408204f1f869d9d6f26b99521",
                              source="epic", external_id="epic:hex_bad"))

    cleaned = db.run_cleanup()
    assert cleaned == 1
    records = db.get_all_game_records()
    assert len(records) == 1
    assert records[0].game.name == "Hades"


def test_cleanup_hex_id_preserves_short_hex(db: Database) -> None:
    """Hex strings shorter than 24 chars must NOT be cleaned up."""
    db.upsert_game(OwnedGame(appid=2_000_000_010, name="abcdef1234567890abcdef12",
                              source="epic", external_id="epic:short"))
    # 24 chars exactly — should match
    cleaned = db.run_cleanup()
    assert cleaned == 1

    db.upsert_game(OwnedGame(appid=2_000_000_011, name="abcdef12345678",
                              source="epic", external_id="epic:tooshort"))
    # 14 chars — should NOT match
    cleaned = db.run_cleanup()
    assert cleaned == 0
    assert len(db.get_all_game_records()) == 1


def test_cleanup_removes_epic_production_names(db: Database) -> None:
    """Games named '<word> Production' with source='epic' must be deleted."""
    db.upsert_game(OwnedGame(appid=2_000_000_020, name="ashishim Production",
                              source="epic", external_id="epic:prod1"))
    db.upsert_game(OwnedGame(appid=2_000_000_021, name="blackcoral Production",
                              source="epic", external_id="epic:prod2"))
    assert len(db.get_all_game_records()) == 2

    cleaned = db.run_cleanup()
    assert cleaned == 2
    assert db.get_all_game_records() == []


def test_cleanup_production_name_removes_appid_mappings(db: Database) -> None:
    """Cleanup must also delete appid_mappings for Production-name entries."""
    db.upsert_game(OwnedGame(appid=2_000_000_020, name="yorkie Production",
                              source="epic", external_id="epic:prod3"))
    db.upsert_appid_mapping("epic", "epic:prod3", "yorkie Production", 12345)

    db.run_cleanup()

    with db._connect() as con:
        count = con.execute(
            "SELECT COUNT(*) FROM appid_mappings"
            " WHERE external_source = 'epic' AND external_id = 'epic:prod3'",
        ).fetchone()[0]
    assert count == 0
    assert db.get_all_game_records() == []


def test_cleanup_preserves_non_production_epic_games(db: Database) -> None:
    """Epic games whose name doesn't match '*Production' must NOT be deleted."""
    db.upsert_game(OwnedGame(appid=2_000_000_020, name="Hades", source="epic",
                              external_id="epic:cat_hades"))
    db.upsert_game(OwnedGame(appid=2_000_000_021, name="ashishim Production",
                              source="epic", external_id="epic:prod_bad"))

    cleaned = db.run_cleanup()
    assert cleaned == 1
    records = db.get_all_game_records()
    assert len(records) == 1
    assert records[0].game.name == "Hades"


def test_cleanup_production_name_ignores_non_epic(db: Database) -> None:
    """Steam games matching the pattern must NOT be touched."""
    db.upsert_game(OwnedGame(appid=999, name="My Production", source="owned"))

    cleaned = db.run_cleanup()
    assert cleaned == 0
    assert len(db.get_all_game_records()) == 1


def test_cleanup_removes_epic_duplicate_external_id(db: Database) -> None:
    """When both a real-appid and a synthetic-appid share external_id, remove the synthetic."""
    db.upsert_game(OwnedGame(appid=570, name="Dota 2", source="epic",
                              external_id="epic:dota_cat"))
    db.upsert_game(OwnedGame(appid=2_000_000_030, name="Dota 2", source="epic",
                              external_id="epic:dota_cat"))
    assert len(db.get_all_game_records()) == 2

    cleaned = db.run_cleanup()
    assert cleaned == 1
    records = db.get_all_game_records()
    assert len(records) == 1
    assert records[0].game.appid == 570


def test_cleanup_duplicate_external_id_removes_appid_mappings(db: Database) -> None:
    """Cleanup must also delete appid_mappings for duplicate synthetic entries."""
    db.upsert_game(OwnedGame(appid=570, name="Dota 2", source="epic",
                              external_id="epic:dota_cat"))
    db.upsert_game(OwnedGame(appid=2_000_000_030, name="Dota 2", source="epic",
                              external_id="epic:dota_cat"))
    db.upsert_appid_mapping("epic", "epic:dota_cat", "Dota 2", 570)

    db.run_cleanup()

    with db._connect() as con:
        count = con.execute(
            "SELECT COUNT(*) FROM appid_mappings"
            " WHERE external_source = 'epic' AND external_id = 'epic:dota_cat'",
        ).fetchone()[0]
    assert count == 0


def test_cleanup_preserves_orphan_synthetic_epic_games(db: Database) -> None:
    """Synthetic-appid games without a real-appid counterpart must NOT be deleted."""
    db.upsert_game(OwnedGame(appid=2_000_000_030, name="Some Indie Game", source="epic",
                              external_id="epic:indie_cat"))

    cleaned = db.run_cleanup()
    assert cleaned == 0
    assert len(db.get_all_game_records()) == 1


def test_cleanup_noop_on_clean_db(db: Database) -> None:
    """Cleanup on an empty or clean DB returns 0."""
    assert db.run_cleanup() == 0
    db.upsert_game(OwnedGame(appid=420, name="Half-Life 2", source="owned"))
    assert db.run_cleanup() == 0


# -- get_diagnostic_summary -------------------------------------------------


def test_get_diagnostic_summary_empty_db(db: Database) -> None:
    """On an empty DB, all counts should be zero."""
    summary = db.get_diagnostic_summary()
    assert summary["total_games"] == 0
    assert summary["enriched_count"] == 0
    assert summary["unenriched_count"] == 0
    assert summary["total_mappings"] == 0
    assert summary["total_alerts"] == 0
    assert summary["total_news"] == 0


def test_get_diagnostic_summary_with_data(db: Database) -> None:
    """Summary should reflect inserted games and details."""
    db.upsert_game(OwnedGame(appid=10, name="CS", source="owned"))
    db.upsert_game(OwnedGame(appid=20, name="TF2", source="owned"))
    db.upsert_game(OwnedGame(
        appid=2_000_000_001, name="Hades", source="epic",
        external_id="epic:cat1",
    ))
    # Enrich only one game
    db.upsert_app_details(AppDetails(
        appid=10, name="Counter-Strike",
    ))

    summary = db.get_diagnostic_summary()
    assert summary["total_games"] == 3
    assert summary["enriched_count"] == 1
    assert summary["unenriched_count"] == 2
    by_source = summary["by_source"]
    assert isinstance(by_source, dict)
    assert by_source.get("owned") == 2
    assert by_source.get("epic") == 1


# -- get_all_appid_mappings -------------------------------------------------


def test_get_all_appid_mappings_empty(db: Database) -> None:
    """Returns an empty list on a fresh DB."""
    assert db.get_all_appid_mappings() == []


def test_get_all_appid_mappings_returns_rows(db: Database) -> None:
    """Inserted mappings should be returned as dicts."""
    db.upsert_appid_mapping("epic", "cat1", "Hades", 1145360)
    db.upsert_appid_mapping("epic", "cat2", "Celeste", None)

    mappings = db.get_all_appid_mappings()
    assert len(mappings) == 2
    resolved = [m for m in mappings if m["steam_appid"] is not None]
    unresolved = [m for m in mappings if m["steam_appid"] is None]
    assert len(resolved) == 1
    assert resolved[0]["external_name"] == "Hades"
    assert len(unresolved) == 1
    assert unresolved[0]["external_name"] == "Celeste"
