"""Tests for steam_tracker.renderer."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from steam_tracker.models import (
    Alert,
    AppDetails,
    DiscoveryStats,
    GameRecord,
    GameStatus,
    NewsItem,
    OwnedGame,
    SkippedItem,
)
from steam_tracker.renderer import (
    _metacritic_html,
    _parse_release_ts,
    _platform_html,
    _price_html,
    format_playtime,
    generate_alerts_html,
    generate_diagnostic_html,
    generate_html,
    make_alert_card,
    make_card,
    write_alerts_html,
    write_diagnostic_html,
    write_html,
)


def test_format_playtime_under_one_hour() -> None:
    assert format_playtime(45) == "45 min"
    assert format_playtime(0) == "0 min"


def test_format_playtime_hours() -> None:
    assert format_playtime(60) == "1h00"
    assert format_playtime(90) == "1h30"
    assert format_playtime(120) == "2h00"
    assert format_playtime(61) == "1h01"


def test_make_card_contains_game_name(sample_record: GameRecord) -> None:
    card = make_card(sample_record)
    assert "Half-Life 2" in card


def test_make_card_contains_badge_class(sample_record: GameRecord) -> None:
    card = make_card(sample_record)
    assert "badge-released" in card


def test_make_card_contains_appid_attribute(sample_record: GameRecord) -> None:
    card = make_card(sample_record)
    assert 'data-appid="420"' in card


def test_make_card_escapes_xss_in_name() -> None:
    record = GameRecord(
        game=OwnedGame(appid=1, name="<script>alert('xss')</script>"),
        status=GameStatus(label="Sorti (1.0)", badge="released", release_date="—"),
    )
    card = make_card(record)
    assert "<script>" not in card
    assert "&lt;script&gt;" in card


def test_make_card_uses_header_image_from_details(sample_record: GameRecord) -> None:
    card = make_card(sample_record)
    assert sample_record.details is not None
    assert sample_record.details.header_image in card


def test_make_card_falls_back_to_cdn_url_when_no_details() -> None:
    record = GameRecord(
        game=OwnedGame(appid=730, name="CS2"),
        status=GameStatus(label="Sorti (1.0)", badge="released", release_date="—"),
    )
    card = make_card(record)
    assert "cdn.akamai.steamstatic.com/steam/apps/730/header.jpg" in card


def test_generate_html_replaces_all_placeholders(sample_record: GameRecord) -> None:
    page = generate_html([sample_record], "76561198000000000")
    placeholders = [
        "__SHARED_JS__", "__GENERATED_AT__", "__STEAM_ID__", "__TOTAL__",
        "__EA__", "__REL__", "__UNREL__", "__CARDS__", "__I18N_JS__",
        "__DIAG_HREF__",
    ]
    for ph in placeholders:
        assert ph not in page, f"Placeholder {ph} not replaced"
    assert "__T_" not in page, "Some __T_ i18n placeholder was not replaced"


def test_generate_html_has_diagnostic_nav_link(sample_record: GameRecord) -> None:
    """Library page should contain a nav link to the diagnostic page."""
    page = generate_html([sample_record], "76561198000000000", diag_href="my_diag.html")
    assert 'href="my_diag.html"' in page


def test_generate_html_stat_counts(sample_record: GameRecord) -> None:
    page = generate_html([sample_record], "76561198000000000")
    # 1 total, 0 EA, 1 released, 0 unreleased
    assert ">1<" in page or ">1 <" in page or "stat-val\">1" in page


# ── New field helpers ─────────────────────────────────────────────────────────

def test_metacritic_html_green_score() -> None:
    html = _metacritic_html(96, "https://metacritic.com/game/half-life-2")
    assert "MC 96" in html
    assert "mc-green" in html
    assert "metacritic.com" in html


def test_metacritic_html_yellow_score() -> None:
    html = _metacritic_html(60, "")
    assert "MC 60" in html
    assert "mc-yellow" in html
    assert "<a " not in html  # no link when url is empty


def test_metacritic_html_red_score() -> None:
    html = _metacritic_html(40, "")
    assert "mc-red" in html


def test_metacritic_html_zero_returns_empty() -> None:
    assert _metacritic_html(0, "") == ""


def test_metacritic_html_has_tooltip_wrapper() -> None:
    html = _metacritic_html(82, "")
    assert "mc-tt-wrap" in html
    assert "mc-tt" in html
    assert "mc-tt-score" in html
    assert "82" in html


def test_metacritic_html_tooltip_label_favorable() -> None:
    html = _metacritic_html(80, "")
    assert "Favorable" in html


def test_metacritic_html_tooltip_label_mixed() -> None:
    html = _metacritic_html(60, "")
    assert "Mixed" in html


def test_metacritic_html_tooltip_label_negative() -> None:
    html = _metacritic_html(30, "")
    assert "Negative" in html


def test_price_html_free_game() -> None:
    d = AppDetails(appid=1, is_free=True)
    assert "Free" in _price_html(d)


def test_price_html_free_game_i18n() -> None:
    d = AppDetails(appid=1, is_free=True)

    def translator(key: str, **kwargs: object) -> str:
        return "Gratuit" if key == "price_free" else key

    assert "Gratuit" in _price_html(d, t=translator)  # type: ignore[arg-type]


def test_price_html_paid_with_discount() -> None:
    d = AppDetails(
        appid=1, price_initial=1999, price_final=999, price_discount_pct=50, price_currency="EUR"
    )
    result = _price_html(d)
    assert "9.99 EUR" in result
    assert "-50%" in result
    assert "price-discount" in result


def test_price_html_paid_no_discount() -> None:
    d = AppDetails(appid=1, price_final=999, price_currency="EUR")
    result = _price_html(d)
    assert "9.99 EUR" in result
    assert "price-discount" not in result


def test_price_html_no_price_returns_empty() -> None:
    d = AppDetails(appid=1)
    assert _price_html(d) == ""


def test_platform_html_all_platforms() -> None:
    d = AppDetails(appid=1, platform_windows=True, platform_mac=True, platform_linux=True)
    result = _platform_html(d)
    assert "🪟" in result
    assert "🍎" in result
    assert "🐧" in result


def test_platform_html_no_platforms_returns_empty() -> None:
    d = AppDetails(appid=1)
    assert _platform_html(d) == ""


def test_make_card_shows_developer(sample_record: GameRecord) -> None:
    card = make_card(sample_record)
    assert "Valve" in card


def test_make_card_shows_genres(sample_record: GameRecord) -> None:
    card = make_card(sample_record)
    assert "genre-tag" in card
    assert "Action" in card


def test_make_card_shows_metacritic(sample_record: GameRecord) -> None:
    card = make_card(sample_record)
    assert "MC 96" in card
    assert "mc-green" in card


def test_make_card_shows_price(sample_record: GameRecord) -> None:
    card = make_card(sample_record)
    assert "9.99 EUR" in card


def test_make_card_shows_platform_icons(sample_record: GameRecord) -> None:
    card = make_card(sample_record)
    assert "🪟" in card


def test_make_card_no_news_section_when_empty() -> None:
    """news-section must be absent when the game has no news (saves vertical space)."""
    record = GameRecord(
        game=OwnedGame(appid=1, name="NoNewsGame"),
        status=GameStatus(label="Sorti", badge="released", release_date="—"),
    )
    card = make_card(record)
    assert "news-section" not in card
    assert "news-toggle" not in card


def test_make_card_news_section_present_when_has_news(sample_record: GameRecord) -> None:
    """news-section (toggle bar) and news-list (overlay) must both be present when
    the game has news; news-list must appear *after* news-section (outside card-body)."""
    card = make_card(sample_record)
    assert len(sample_record.news) > 0
    assert "news-section" in card
    assert "news-toggle" in card
    assert "news-list" in card
    # news-list must be placed after news-section (not nested inside it)
    assert card.index('"news-section"') < card.index('"news-list"')


def test_make_card_appid_not_in_body_text(sample_record: GameRecord) -> None:
    """AppID should be a data attribute only; the visible text '#<appid>' is removed."""
    card = make_card(sample_record)
    # data-appid attribute must still be present
    assert 'data-appid="420"' in card
    # The old visible span (#appid) must be gone
    assert "#420" not in card


def test_generate_html_uses_aspect_ratio_for_card_img() -> None:
    """Card images must use aspect-ratio: 460 / 215, not a fixed height."""
    page = generate_html([], "76561198000000000")
    assert "aspect-ratio: 460 / 215" in page
    # The old fixed 80px height must be gone
    assert "height: 80px" not in page


# ── _parse_release_ts ─────────────────────────────────────────────────────────

def test_parse_release_ts_standard_date() -> None:
    ts = _parse_release_ts("01 Jan 2020")
    assert ts == int(datetime(2020, 1, 1, tzinfo=UTC).timestamp())


def test_parse_release_ts_french_month() -> None:
    ts = _parse_release_ts("23 septembre 2023")
    assert ts == int(datetime(2023, 9, 23, tzinfo=UTC).timestamp())


def test_parse_release_ts_year_only() -> None:
    ts = _parse_release_ts("2024")
    assert ts == int(datetime(2024, 1, 1, tzinfo=UTC).timestamp())


def test_parse_release_ts_year_in_text_fallback() -> None:
    ts = _parse_release_ts("Q1 2025")
    assert ts == int(datetime(2025, 1, 1, tzinfo=UTC).timestamp())


def test_parse_release_ts_empty_returns_zero() -> None:
    assert _parse_release_ts("") == 0
    assert _parse_release_ts("\u2014") == 0


# ── make_card — news timestamps ───────────────────────────────────────────────

def test_make_card_sets_patchnote_timestamp(sample_record: GameRecord) -> None:
    # sample_record has a news item with tags=["patchnotes", "valve"]
    card = make_card(sample_record)
    expected_ts = str(int(sample_record.news[0].date.timestamp()))
    assert f'data-last-patch-ts="{expected_ts}"' in card


def test_make_card_no_news_has_zero_timestamps() -> None:
    record = GameRecord(
        game=OwnedGame(appid=1, name="Empty"),
        status=GameStatus(label="Sorti", badge="released", release_date="\u2014"),
    )
    card = make_card(record)
    assert 'data-last-update="0"' in card
    assert 'data-last-patch-ts="0"' in card
    assert 'data-last-other-ts="0"' in card


def test_make_card_other_news_sets_last_other_ts() -> None:
    news = [
        NewsItem(
            gid="1",
            title="Announcement",
            date=datetime(2024, 6, 1, tzinfo=UTC),
            url="https://example.com/1",
            author="Dev",
            feedname="a",
            feedlabel="A",
            tags=["announcement"],
        )
    ]
    record = GameRecord(
        game=OwnedGame(appid=1, name="Game"),
        status=GameStatus(label="Sorti", badge="released", release_date="\u2014"),
        news=news,
    )
    card = make_card(record)
    expected_ts = str(int(news[0].date.timestamp()))
    assert f'data-last-other-ts="{expected_ts}"' in card
    assert 'data-last-patch-ts="0"' in card


# ── write_html ────────────────────────────────────────────────────────────────


def test_write_html_creates_file(sample_record: GameRecord, tmp_path: Path) -> None:
    out = tmp_path / "lib.html"
    write_html([sample_record], "76561198000000000", out)
    assert out.exists()
    assert "Half-Life 2" in out.read_text(encoding="utf-8")


# ── Epic source display ───────────────────────────────────────────────────────

def _epic_record() -> GameRecord:
    """An Epic-only game with a hash-based appid (no Steam enrichment)."""
    return GameRecord(
        game=OwnedGame(
            appid=2_047_593_821,
            name="Fortnite",
            source="epic",
            external_id="epic:abc123CatalogId",
        ),
        status=GameStatus(label="—", badge="unknown", release_date="—"),
    )


def test_make_card_epic_has_data_store_epic() -> None:
    card = make_card(_epic_record())
    assert 'data-store="epic"' in card
    assert 'data-lib-status="owned"' in card


def test_make_card_epic_hint_is_epic_not_steam() -> None:
    card = make_card(_epic_record())
    assert "🎮 Epic" in card
    assert "↗ Steam" not in card


def test_make_card_epic_playtime_shows_epic_label() -> None:
    card = make_card(_epic_record())
    # Should show the Epic source label, not the "🕹 Xh" playtime format
    assert "🎮 Epic" in card
    assert "🕹" not in card


def test_make_card_steam_owned_hint_is_steam() -> None:
    record = GameRecord(
        game=OwnedGame(appid=420, name="HL2", playtime_forever=120),
        status=GameStatus(label="—", badge="released", release_date="—"),
    )
    card = make_card(record)
    assert "↗ Steam" in card


def test_make_card_steam_owned_has_data_store_steam() -> None:
    record = GameRecord(
        game=OwnedGame(appid=420, name="HL2", playtime_forever=120, source="owned"),
        status=GameStatus(label="—", badge="released", release_date="—"),
    )
    card = make_card(record)
    assert 'data-store="steam"' in card
    assert 'data-lib-status="owned"' in card


def test_make_card_wishlist_has_data_lib_status_wishlist() -> None:
    record = GameRecord(
        game=OwnedGame(appid=730, name="CS2", source="wishlist"),
        status=GameStatus(label="—", badge="released", release_date="—"),
    )
    card = make_card(record)
    assert 'data-store="steam"' in card
    assert 'data-lib-status="wishlist"' in card


def test_make_card_followed_has_data_lib_status_followed() -> None:
    record = GameRecord(
        game=OwnedGame(appid=570, name="Dota 2", source="followed"),
        status=GameStatus(label="—", badge="released", release_date="—"),
    )
    card = make_card(record)
    assert 'data-store="steam"' in card
    assert 'data-lib-status="followed"' in card


def test_generate_html_has_steam_store_filter_button() -> None:
    page = generate_html([_epic_record()], "0")
    assert 'class="store-btn active" data-store="steam"' in page


def test_generate_html_has_epic_store_filter_button() -> None:
    page = generate_html([_epic_record()], "0")
    assert 'class="store-btn active" data-store="epic"' in page


def test_generate_html_has_followed_collection_filter_button() -> None:
    page = generate_html([_epic_record()], "0")
    assert 'class="filter-btn" data-lib-status="followed"' in page


# ── make_alert_card ──────────────────────────────────────────────────────────


def _sample_alert() -> Alert:
    return Alert(
        id="abc123def456abcd",
        rule_name="Version Update",
        rule_icon="🔧",
        appid=420,
        game_name="Half-Life 2",
        timestamp=datetime(2024, 6, 1, tzinfo=UTC),
        title="Build 12345 deployed",
        details="buildid changed: 11111 → 12345",
        url="",
        source_type="field_change",
        source_id="420:buildid:2024-06-01",
    )


def test_make_alert_card_contains_game_name(sample_record: GameRecord) -> None:
    card = make_alert_card(_sample_alert(), sample_record)
    assert "Half-Life 2" in card


def test_make_alert_card_contains_rule_name() -> None:
    card = make_alert_card(_sample_alert())
    assert "Version Update" in card


def test_make_alert_card_contains_icon() -> None:
    card = make_alert_card(_sample_alert())
    assert "🔧" in card


def test_make_alert_card_has_data_id() -> None:
    alert = _sample_alert()
    card = make_alert_card(alert)
    assert f'data-id="{alert.id}"' in card


def test_make_alert_card_escapes_xss_in_game_name() -> None:
    alert = Alert(
        id="xss123456789012",
        rule_name="Test",
        rule_icon="✓",
        appid=1,
        game_name='<script>alert("xss")</script>',
        timestamp=datetime(2024, 1, 1, tzinfo=UTC),
        title="<script>xss</script>",
        details="",
        url="",
        source_type="news",
        source_id="1",
    )
    card = make_alert_card(alert)
    assert "<script>" not in card
    assert "&lt;script&gt;" in card


def test_make_alert_card_has_store_and_collection_attrs(sample_record: GameRecord) -> None:
    """Cards carry data-store / data-lib-status for JS filtering."""
    card = make_alert_card(_sample_alert(), sample_record)
    assert 'data-store="steam"' in card
    assert 'data-lib-status="owned"' in card


def test_make_alert_card_epic_store_tag() -> None:
    """An Epic game should produce data-store='epic'."""
    epic_game = OwnedGame(appid=999, name="Epic Game", source="epic")
    record = GameRecord(
        game=epic_game,
        details=None,
        news=[],
        status=GameStatus(label="Released", badge="released", release_date="2024"),
    )
    card = make_alert_card(_sample_alert(), record)
    assert 'data-store="epic"' in card
    assert 'data-lib-status="owned"' in card


def test_make_alert_card_wishlist_collection_tag() -> None:
    """A wishlist game should produce data-lib-status='wishlist'."""
    wl_game = OwnedGame(appid=420, name="Half-Life 2", source="wishlist")
    record = GameRecord(
        game=wl_game,
        details=None,
        news=[],
        status=GameStatus(label="Released", badge="released", release_date="2024"),
    )
    card = make_alert_card(_sample_alert(), record)
    assert 'data-lib-status="wishlist"' in card


def test_make_alert_card_shows_buildid(sample_record: GameRecord) -> None:
    """When the game has a non-zero buildid, a badge is displayed."""
    assert sample_record.details is not None
    sample_record.details.buildid = 12345
    card = make_alert_card(_sample_alert(), sample_record)
    assert "build 12345" in card


def test_make_alert_card_no_buildid_when_zero(sample_record: GameRecord) -> None:
    """No buildid badge when buildid is 0."""
    assert sample_record.details is not None
    sample_record.details.buildid = 0
    card = make_alert_card(_sample_alert(), sample_record)
    assert "alert-buildid" not in card


def test_make_alert_card_has_store_url_attr() -> None:
    """Card should carry a data-store-url pointing to the Steam store."""
    card = make_alert_card(_sample_alert())
    assert 'data-store-url="https://store.steampowered.com/app/420"' in card


def test_make_alert_card_has_news_url_attr() -> None:
    """Card with alert.url carries data-news-url for JS click handler."""
    alert = _sample_alert()
    alert.url = "https://example.com/news"
    card = make_alert_card(alert)
    assert 'data-news-url="https://example.com/news"' in card




# -- data-unknown attribute -------------------------------------------------


def test_make_card_unknown_flag_set_for_synthetic_appid() -> None:
    """Cards with synthetic appid (>= 2B) must have data-unknown='true'."""
    record = GameRecord(
        game=OwnedGame(appid=2_000_000_001, name="Unknown Game", source="epic",
                        external_id="epic:cat1"),
        status=GameStatus(label="—", badge="unknown", release_date="—"),
    )
    card = make_card(record)
    assert 'data-unknown="true"' in card


def test_make_card_unknown_flag_absent_for_real_appid() -> None:
    """Cards with real appid (< 2B) must NOT have data-unknown."""
    record = GameRecord(
        game=OwnedGame(appid=420, name="Half-Life 2"),
        status=GameStatus(label="—", badge="released", release_date="—"),
    )
    card = make_card(record)
    assert "data-unknown" not in card


def test_make_card_unknown_flag_set_for_real_appid_no_details() -> None:
    """Cards with real appid but badge='unknown' (no details) must have data-unknown."""
    record = GameRecord(
        game=OwnedGame(appid=31292, name="Dishonored - Definitive Edition",
                        source="epic", external_id="epic:abc123"),
        status=GameStatus(label="Inconnu", badge="unknown", release_date="—"),
    )
    card = make_card(record)
    assert 'data-unknown="true"' in card


def test_make_alert_card_unknown_flag_set_for_synthetic_appid() -> None:
    """Alert cards with synthetic appid must have data-unknown='true'."""
    alert = Alert(
        id="a1", appid=2_000_000_001, game_name="Unknown Game",
        rule_name="version_update", rule_icon="🔧",
        title="Version Update", details="v1→v2",
        source_type="field_change",
        timestamp=datetime(2024, 1, 15, tzinfo=UTC),
    )
    card = make_alert_card(alert)
    assert 'data-unknown="true"' in card


def test_make_alert_card_unknown_flag_absent_for_real_appid() -> None:
    """Alert cards with real appid must NOT have data-unknown."""
    card = make_alert_card(_sample_alert())
    assert "data-unknown" not in card


def test_make_alert_card_unknown_flag_set_for_real_appid_unknown_status() -> None:
    """Alert cards with real appid but unknown status must have data-unknown."""
    alert = Alert(
        id="a2", appid=31292, game_name="Dishonored - Definitive Edition",
        rule_name="version_update", rule_icon="🔧",
        title="Version Update", details="v1→v2",
        source_type="field_change",
        timestamp=datetime(2024, 1, 15, tzinfo=UTC),
    )
    record = GameRecord(
        game=OwnedGame(appid=31292, name="Dishonored - Definitive Edition",
                        source="epic", external_id="epic:abc123"),
        status=GameStatus(label="Inconnu", badge="unknown", release_date="—"),
    )
    card = make_alert_card(alert, record=record)
    assert 'data-unknown="true"' in card


# -- Diagnostic page with unknown games -------------------------------------


def test_generate_diagnostic_html_with_unknown_games() -> None:
    """Unknown games should appear in the diagnostic output."""
    unknown = [
        GameRecord(
            game=OwnedGame(appid=2_000_000_001, name="Mystery Game", source="epic",
                            external_id="epic:cat99"),
            status=GameStatus(label="—", badge="unknown", release_date="—"),
        ),
    ]
    html = generate_diagnostic_html(_EMPTY_SUMMARY, [], unknown_games=unknown)
    assert "Mystery Game" in html
    assert "epic:cat99" in html
    assert "2000000001" in html


def test_generate_diagnostic_html_no_unknown_games() -> None:
    """When no unknown games, the 'no unknown' message should appear."""
    html = generate_diagnostic_html(_EMPTY_SUMMARY, [], unknown_games=[])
    assert "No unknown games" in html or "Aucun jeu inconnu" in html


def test_generate_diagnostic_html_unknown_games_none() -> None:
    """When unknown_games is None, no error should occur."""
    html = generate_diagnostic_html(_EMPTY_SUMMARY, [])
    assert "__UNKNOWN_CONTENT__" not in html


# -- date-added attribute ---------------------------------------------------


def test_make_card_contains_time_added_attribute(sample_record: GameRecord) -> None:
    """Game card must carry a data-time-added attribute."""
    record = sample_record.model_copy(update={"time_added": 1700000000})
    card = make_card(record)
    assert 'data-time-added="1700000000"' in card


def test_generate_html_has_dateadded_sort_option(sample_record: GameRecord) -> None:
    """The sort dropdown must include a 'dateadded' option."""
    html = generate_html([sample_record], steam_id="123")
    assert 'value="dateadded"' in html


def test_make_alert_card_no_news_url_when_empty() -> None:
    """Card without alert.url must not have data-news-url."""
    alert = _sample_alert()
    alert.url = ""
    card = make_alert_card(alert)
    assert "data-news-url" not in card


def test_make_alert_card_game_name_is_link() -> None:
    """Game name should be an <a> tag linking to the store page."""
    card = make_alert_card(_sample_alert())
    assert 'class="alert-game"' in card
    assert 'href="https://store.steampowered.com/app/420"' in card


def test_make_alert_card_thumb_is_link() -> None:
    """Thumbnail image should be wrapped in an <a> linking to the store page."""
    card = make_alert_card(_sample_alert())
    assert 'class="alert-thumb-link"' in card


def test_generate_alerts_html_has_nav_in_toolbar(sample_record: GameRecord) -> None:
    """Nav link to library must be in the toolbar, not in the header."""
    page = generate_alerts_html([_sample_alert()], [sample_record], "76561198000000000")
    # The link should be inside the toolbar <div class="toolbar">...</div>
    import re
    toolbar = re.search(r'<div class="toolbar">.*?</div>\s*<main>', page, re.DOTALL)
    assert toolbar is not None
    assert "steam_library.html" in toolbar.group()


def test_generate_alerts_html_has_store_filter_buttons(sample_record: GameRecord) -> None:
    """Alerts page should have store filter buttons."""
    page = generate_alerts_html([_sample_alert()], [sample_record], "76561198000000000")
    assert 'data-store="steam"' in page
    assert 'data-store="epic"' in page
    assert "store-btn" in page


def test_generate_alerts_html_has_collection_filter_buttons(sample_record: GameRecord) -> None:
    """Alerts page should have lib-status filter buttons."""
    page = generate_alerts_html([_sample_alert()], [sample_record], "76561198000000000")
    assert 'data-lib-status="all"' in page
    assert 'data-lib-status="owned"' in page
    assert 'data-lib-status="wishlist"' in page
    assert 'data-lib-status="followed"' in page


# ── generate_alerts_html ──────────────────────────────────────────────────────


def test_generate_alerts_html_replaces_all_placeholders(sample_record: GameRecord) -> None:
    page = generate_alerts_html([_sample_alert()], [sample_record], "76561198000000000")
    for ph in ["__GENERATED_AT__", "__STEAM_ID__", "__LIB_HREF__", "__ALERTS__",
               "__T_", "__I18N_", "__DIAG_HREF__"]:
        assert ph not in page, f"Placeholder {ph!r} still present in output"


def test_generate_alerts_html_has_diagnostic_nav_link(sample_record: GameRecord) -> None:
    """Alerts page should contain a nav link to the diagnostic page."""
    page = generate_alerts_html([_sample_alert()], [sample_record], "76561198000000000",
                                diag_href="my_diag.html")
    assert 'href="my_diag.html"' in page


def test_generate_alerts_html_contains_alert_title(sample_record: GameRecord) -> None:
    page = generate_alerts_html([_sample_alert()], [sample_record], "76561198000000000")
    assert "Build 12345 deployed" in page


def test_generate_alerts_html_empty_list(sample_record: GameRecord) -> None:
    page = generate_alerts_html([], [sample_record], "76561198000000000")
    assert "__ALERTS__" not in page


def test_write_alerts_html_creates_file(sample_record: GameRecord, tmp_path: Path) -> None:
    out = tmp_path / "alerts.html"
    write_alerts_html([_sample_alert()], [sample_record], "76561198000000000", out)
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "Half-Life 2" in content
    assert "Build 12345 deployed" in content


# -- Diagnostic page --------------------------------------------------------

_EMPTY_SUMMARY: dict[str, object] = {
    "total_games": 0,
    "enriched_count": 0,
    "unenriched_count": 0,
    "by_source": {},
    "total_mappings": 0,
    "resolved_mappings": 0,
    "unresolved_mappings": 0,
    "manual_mappings": 0,
    "total_alerts": 0,
    "total_news": 0,
}


def test_generate_diagnostic_html_basic() -> None:
    """Diagnostic page should contain key section headings."""
    html = generate_diagnostic_html(_EMPTY_SUMMARY, [], [])
    assert "SteamPulse" in html
    # No unresolved placeholders
    assert "__T_" not in html


def test_generate_diagnostic_html_with_mappings() -> None:
    """Mapping rows should appear in the output."""
    mappings: list[dict[str, object]] = [
        {
            "external_source": "epic",
            "external_id": "cat1",
            "external_name": "Hades",
            "steam_appid": 1145360,
            "resolved_at": "2025-01-01",
            "manual": 0,
        },
    ]
    html = generate_diagnostic_html(_EMPTY_SUMMARY, mappings, [])
    assert "Hades" in html
    assert "1145360" in html


def test_generate_diagnostic_html_with_discovery_stats() -> None:
    """Epic discovery stats should appear in the output."""
    stats = [DiscoveryStats(
        total_api_items=100,
        accepted_count=80,
        resolved_count=70,
        unresolved_count=10,
        skipped_items=[
            SkippedItem(catalog_id="cat_x", raw_name="abc123def", reason="hex_id"),
        ],
    )]
    html = generate_diagnostic_html(_EMPTY_SUMMARY, [], stats)
    assert "100" in html
    assert "abc123def" in html


def test_generate_diagnostic_html_french() -> None:
    """Page should use French translation when lang=fr."""
    html = generate_diagnostic_html(_EMPTY_SUMMARY, [], [], lang="fr")
    # French title from i18n
    assert "Diagnostic" in html


def test_write_diagnostic_html_creates_file(tmp_path: Path) -> None:
    """write_diagnostic_html should create the output file."""
    out = tmp_path / "steam_diagnostic.html"
    write_diagnostic_html(_EMPTY_SUMMARY, [], out)
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "SteamPulse" in content


def test_generate_diagnostic_html_mapping_cards_have_data_filter() -> None:
    """Mapping stat cards should have data-filter attributes for click filtering."""
    summary = {**_EMPTY_SUMMARY, "total_mappings": 3, "resolved_mappings": 2,
               "unresolved_mappings": 1, "manual_mappings": 0}
    html = generate_diagnostic_html(summary, [], [])
    assert 'data-filter="all"' in html
    assert 'data-filter="resolved"' in html
    assert 'data-filter="unresolved"' in html
    assert 'data-filter="manual"' in html


def test_generate_diagnostic_html_mapping_rows_have_data_status() -> None:
    """Mapping table rows should have data-status for JS filtering."""
    mappings: list[dict[str, object]] = [
        {"external_source": "epic", "external_id": "c1", "external_name": "Hades",
         "steam_appid": 1145360, "resolved_at": "2025-01-01", "manual": 0},
        {"external_source": "epic", "external_id": "c2", "external_name": "Unknown",
         "steam_appid": None, "resolved_at": "", "manual": 0},
        {"external_source": "epic", "external_id": "c3", "external_name": "Custom",
         "steam_appid": 999, "resolved_at": "2025-01-01", "manual": 1},
    ]
    html = generate_diagnostic_html(_EMPTY_SUMMARY, mappings, [])
    assert 'data-status="resolved"' in html
    assert 'data-status="unresolved"' in html
    assert 'data-status="manual"' in html


def test_generate_diagnostic_html_contains_toggle_script() -> None:
    """The diagnostic page should include the toggleFilter JS function."""
    html = generate_diagnostic_html(_EMPTY_SUMMARY, [], [])
    assert "toggleFilter" in html
    assert "activeFilter" in html


# ── soft-delete / availability filter ─────────────────────────────────────────


def test_make_card_removed_has_data_attribute() -> None:
    """A removed game card must carry data-removed=\"1\"."""
    record = GameRecord(
        game=OwnedGame(appid=1, name="Delisted"),
        status=GameStatus(label="—", badge="released", release_date="—"),
        removed_at="2024-01-01T00:00:00+00:00",
    )
    card = make_card(record)
    assert 'data-removed="1"' in card


def test_make_card_active_has_no_removed_attribute() -> None:
    """An active game card must NOT carry data-removed."""
    record = GameRecord(
        game=OwnedGame(appid=1, name="Active"),
        status=GameStatus(label="—", badge="released", release_date="—"),
        removed_at=None,
    )
    card = make_card(record)
    assert "data-removed" not in card


def test_make_card_removed_has_badge_removed_class() -> None:
    """A removed game card must contain a badge with class badge-removed."""
    record = GameRecord(
        game=OwnedGame(appid=1, name="Delisted"),
        status=GameStatus(label="—", badge="released", release_date="—"),
        removed_at="2024-03-15T12:00:00+00:00",
    )
    card = make_card(record)
    assert "badge-removed" in card


def test_generate_html_has_availability_filter_group() -> None:
    """Library page must contain the availability filter panel with availBtns."""
    record = GameRecord(
        game=OwnedGame(appid=1, name="Game"),
        status=GameStatus(label="—", badge="released", release_date="—"),
    )
    page = generate_html([record], steam_id="123")
    assert 'id="availBtns"' in page
    assert 'data-avail="active"' in page
    assert 'data-avail="removed"' in page
    assert 'data-avail="all"' in page

