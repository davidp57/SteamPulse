"""Tests for steam_tracker.alerts."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from steam_tracker.alerts import AlertEngine
from steam_tracker.db import Database
from steam_tracker.models import AlertRule, AppDetails, FieldChange, NewsItem, OwnedGame


@pytest.fixture()
def news_rule() -> AlertRule:
    return AlertRule(
        name="Version Update",
        rule_type="news_keyword",
        icon="🔄",
        keywords=["patch notes", "update"],
        match="title",
    )


@pytest.fixture()
def all_news_rule() -> AlertRule:
    return AlertRule(
        name="All News",
        rule_type="news_keyword",
        icon="📰",
        keywords=[],
        builtin=True,
    )


@pytest.fixture()
def price_rule() -> AlertRule:
    return AlertRule(
        name="Price Drop",
        rule_type="state_change",
        icon="💰",
        field="price_final",
        condition="decreased",
    )


@pytest.fixture()
def appeared_rule() -> AlertRule:
    return AlertRule(
        name="New Score",
        rule_type="state_change",
        icon="⭐",
        field="metacritic_score",
        condition="appeared",
    )


@pytest.fixture()
def changed_rule() -> AlertRule:
    return AlertRule(
        name="Silent Update",
        rule_type="state_change",
        icon="🔧",
        field="buildid",
        condition="changed",
    )


@pytest.fixture()
def alert_db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "test_alerts.db")
    db.upsert_game(OwnedGame(appid=420, name="Half-Life 2"))
    return db


@pytest.fixture()
def sample_news_item() -> NewsItem:
    return NewsItem(
        gid="abc123",
        title="Patch Notes v1.2.3 update",
        date=datetime(2024, 1, 15, tzinfo=UTC),
        url="https://store.steampowered.com/news/app/420/view/1",
    )


# ── evaluate_news ──────────────────────────────────────────────────────────────

def test_evaluate_news_keyword_match_title(
    news_rule: AlertRule, alert_db: Database, sample_news_item: NewsItem
) -> None:
    engine = AlertEngine([news_rule], alert_db)
    alerts = engine.evaluate_news(420, "Half-Life 2", [sample_news_item])
    assert len(alerts) == 1
    assert alerts[0].rule_name == "Version Update"


def test_evaluate_news_keyword_no_match(
    news_rule: AlertRule, alert_db: Database
) -> None:
    engine = AlertEngine([news_rule], alert_db)
    news = [
        NewsItem(
            gid="xyz",
            title="Dev blog: future plans",
            date=datetime(2024, 1, 15, tzinfo=UTC),
            url="https://example.com/news/1",
        )
    ]
    alerts = engine.evaluate_news(420, "Half-Life 2", news)
    assert alerts == []


def test_evaluate_news_all_news_rule_matches_everything(
    all_news_rule: AlertRule, alert_db: Database, sample_news_item: NewsItem
) -> None:
    engine = AlertEngine([all_news_rule], alert_db)
    alerts = engine.evaluate_news(420, "Half-Life 2", [sample_news_item])
    assert len(alerts) == 1
    assert alerts[0].rule_name == "All News"


def test_evaluate_news_multiple_rules_can_match_same_item(
    news_rule: AlertRule, all_news_rule: AlertRule,
    alert_db: Database, sample_news_item: NewsItem
) -> None:
    engine = AlertEngine([news_rule, all_news_rule], alert_db)
    alerts = engine.evaluate_news(420, "Half-Life 2", [sample_news_item])
    rule_names = {a.rule_name for a in alerts}
    assert "Version Update" in rule_names
    assert "All News" in rule_names


def test_evaluate_news_disabled_rule_skipped(
    news_rule: AlertRule, alert_db: Database, sample_news_item: NewsItem
) -> None:
    news_rule.enabled = False
    engine = AlertEngine([news_rule], alert_db)
    alerts = engine.evaluate_news(420, "Half-Life 2", [sample_news_item])
    assert alerts == []


def test_evaluate_news_alert_id_is_deterministic(
    all_news_rule: AlertRule, alert_db: Database, sample_news_item: NewsItem
) -> None:
    engine = AlertEngine([all_news_rule], alert_db)
    a1 = engine.evaluate_news(420, "Half-Life 2", [sample_news_item])
    a2 = engine.evaluate_news(420, "Half-Life 2", [sample_news_item])
    assert a1[0].id == a2[0].id


def test_evaluate_news_alert_source_type_is_news(
    all_news_rule: AlertRule, alert_db: Database, sample_news_item: NewsItem
) -> None:
    engine = AlertEngine([all_news_rule], alert_db)
    alerts = engine.evaluate_news(420, "Half-Life 2", [sample_news_item])
    assert alerts[0].source_type == "news"
    assert alerts[0].source_id == sample_news_item.gid


def test_evaluate_news_case_insensitive_keyword(
    alert_db: Database, sample_news_item: NewsItem
) -> None:
    rule = AlertRule(
        name="Test",
        rule_type="news_keyword",
        keywords=["PATCH NOTES"],
        match="title",
    )
    engine = AlertEngine([rule], alert_db)
    alerts = engine.evaluate_news(420, "Half-Life 2", [sample_news_item])
    assert len(alerts) == 1


# ── evaluate_field_changes ────────────────────────────────────────────────────

def test_evaluate_field_changes_decreased_condition(
    price_rule: AlertRule, alert_db: Database
) -> None:
    ts = datetime(2024, 1, 15, tzinfo=UTC)
    changes = [
        FieldChange(
            appid=420, field_name="price_final", old_value="999", new_value="499", timestamp=ts
        ),
    ]
    engine = AlertEngine([price_rule], alert_db)
    alerts = engine.evaluate_field_changes(420, "Half-Life 2", changes)
    assert len(alerts) == 1
    assert alerts[0].rule_name == "Price Drop"


def test_evaluate_field_changes_decreased_no_match_when_increased(
    price_rule: AlertRule, alert_db: Database
) -> None:
    ts = datetime(2024, 1, 15, tzinfo=UTC)
    changes = [
        FieldChange(
            appid=420, field_name="price_final", old_value="499", new_value="999", timestamp=ts
        ),
    ]
    engine = AlertEngine([price_rule], alert_db)
    alerts = engine.evaluate_field_changes(420, "Half-Life 2", changes)
    assert alerts == []


def test_evaluate_field_changes_appeared_condition(
    appeared_rule: AlertRule, alert_db: Database
) -> None:
    ts = datetime(2024, 1, 15, tzinfo=UTC)
    changes = [
        FieldChange(
            appid=420, field_name="metacritic_score", old_value=None, new_value="85", timestamp=ts
        ),
    ]
    engine = AlertEngine([appeared_rule], alert_db)
    alerts = engine.evaluate_field_changes(420, "Half-Life 2", changes)
    assert len(alerts) == 1


def test_evaluate_field_changes_appeared_no_match_when_was_nonzero(
    appeared_rule: AlertRule, alert_db: Database
) -> None:
    ts = datetime(2024, 1, 15, tzinfo=UTC)
    changes = [
        FieldChange(
            appid=420, field_name="metacritic_score", old_value="80", new_value="85", timestamp=ts
        ),
    ]
    engine = AlertEngine([appeared_rule], alert_db)
    alerts = engine.evaluate_field_changes(420, "Half-Life 2", changes)
    assert alerts == []


def test_evaluate_field_changes_changed_condition(
    changed_rule: AlertRule, alert_db: Database
) -> None:
    ts = datetime(2024, 1, 15, tzinfo=UTC)
    changes = [
        FieldChange(
            appid=420, field_name="buildid", old_value="1000", new_value="1001", timestamp=ts
        ),
    ]
    engine = AlertEngine([changed_rule], alert_db)
    alerts = engine.evaluate_field_changes(420, "Half-Life 2", changes)
    assert len(alerts) == 1


def test_evaluate_field_changes_wrong_field_no_match(
    changed_rule: AlertRule, alert_db: Database
) -> None:
    ts = datetime(2024, 1, 15, tzinfo=UTC)
    changes = [
        FieldChange(appid=420, field_name="name", old_value="Old", new_value="New", timestamp=ts),
    ]
    engine = AlertEngine([changed_rule], alert_db)
    alerts = engine.evaluate_field_changes(420, "Half-Life 2", changes)
    assert alerts == []


def test_evaluate_field_changes_alert_id_is_deterministic(
    changed_rule: AlertRule, alert_db: Database
) -> None:
    ts = datetime(2024, 1, 15, tzinfo=UTC)
    changes = [
        FieldChange(
            appid=420, field_name="buildid", old_value="1000", new_value="1001", timestamp=ts
        ),
    ]
    engine = AlertEngine([changed_rule], alert_db)
    a1 = engine.evaluate_field_changes(420, "Half-Life 2", changes)
    a2 = engine.evaluate_field_changes(420, "Half-Life 2", changes)
    assert a1[0].id == a2[0].id


def test_evaluate_field_changes_alert_source_type(
    changed_rule: AlertRule, alert_db: Database
) -> None:
    ts = datetime(2024, 1, 15, tzinfo=UTC)
    changes = [
        FieldChange(
            appid=420, field_name="buildid", old_value="1000", new_value="1001", timestamp=ts
        ),
    ]
    engine = AlertEngine([changed_rule], alert_db)
    alerts = engine.evaluate_field_changes(420, "Half-Life 2", changes)
    assert alerts[0].source_type == "field_change"


def test_evaluate_field_changes_disabled_rule_skipped(
    changed_rule: AlertRule, alert_db: Database
) -> None:
    changed_rule.enabled = False
    ts = datetime(2024, 1, 15, tzinfo=UTC)
    changes = [
        FieldChange(
            appid=420, field_name="buildid", old_value="1000", new_value="1001", timestamp=ts
        ),
    ]
    engine = AlertEngine([changed_rule], alert_db)
    alerts = engine.evaluate_field_changes(420, "Half-Life 2", changes)
    assert alerts == []


# ── DB round-trip ──────────────────────────────────────────────────────────────

def test_upsert_alert_idempotent(
    all_news_rule: AlertRule, alert_db: Database, sample_news_item: NewsItem
) -> None:
    engine = AlertEngine([all_news_rule], alert_db)
    alerts = engine.evaluate_news(420, "Half-Life 2", [sample_news_item])
    alert_db.upsert_alert(alerts[0])
    alert_db.upsert_alert(alerts[0])  # duplicate — should be ignored
    stored = alert_db.get_alerts()
    assert len(stored) == 1


def test_get_alerts_filter_by_rule(
    all_news_rule: AlertRule, news_rule: AlertRule,
    alert_db: Database, sample_news_item: NewsItem
) -> None:
    engine = AlertEngine([all_news_rule, news_rule], alert_db)
    alerts = engine.evaluate_news(420, "Half-Life 2", [sample_news_item])
    for a in alerts:
        alert_db.upsert_alert(a)
    by_rule = alert_db.get_alerts(rule_name="All News")
    assert all(a.rule_name == "All News" for a in by_rule)


def test_get_alert_count_by_rule(
    all_news_rule: AlertRule, alert_db: Database, sample_news_item: NewsItem
) -> None:
    engine = AlertEngine([all_news_rule], alert_db)
    alerts = engine.evaluate_news(420, "Half-Life 2", [sample_news_item])
    alert_db.upsert_alert(alerts[0])
    counts = alert_db.get_alert_count_by_rule()
    assert counts.get("All News", 0) == 1


# ── backfill ───────────────────────────────────────────────────────────────────

def test_backfill_creates_alerts_from_field_history(
    changed_rule: AlertRule, alert_db: Database
) -> None:
    # Insert initial details (all fields appear as new)
    d1 = AppDetails(appid=420, buildid=1000)
    alert_db.upsert_app_details(d1)
    # Update buildid (triggers change)
    d2 = AppDetails(appid=420, buildid=1001)
    alert_db.upsert_app_details(d2)

    engine = AlertEngine([changed_rule], alert_db)
    count = engine.backfill()
    assert count > 0
    stored = alert_db.get_alerts(rule_name="Silent Update")
    assert len(stored) == count
