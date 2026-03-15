"""Tests for steam_tracker.renderer."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from steam_tracker.models import AppDetails, GameRecord, GameStatus, NewsItem, OwnedGame
from steam_tracker.renderer import (
    _metacritic_html,
    _parse_release_ts,
    _platform_html,
    _price_html,
    format_playtime,
    generate_html,
    generate_news_html,
    make_card,
    make_news_row,
    write_html,
    write_news_html,
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
    for ph in ["__SHARED_JS__", "__GENERATED_AT__", "__STEAM_ID__", "__TOTAL__", "__EA__", "__REL__", "__UNREL__",
               "__CARDS__", "__I18N_JS__"]:
        assert ph not in page, f"Placeholder {ph} not replaced"
    assert "__T_" not in page, "Some __T_ i18n placeholder was not replaced"


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


def test_price_html_free_game() -> None:
    d = AppDetails(appid=1, is_free=True)
    assert "Free" in _price_html(d)


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


# ── make_news_row ─────────────────────────────────────────────────────────────

def test_make_news_row_contains_game_name(sample_record: GameRecord) -> None:
    row = make_news_row(sample_record, sample_record.news[0])
    assert "Half-Life 2" in row


def test_make_news_row_marks_patchnotes_tag(sample_record: GameRecord) -> None:
    row = make_news_row(sample_record, sample_record.news[0])
    assert 'data-tag="patchnotes"' in row
    assert "feed-tag-patchnotes" in row


def test_make_news_row_marks_other_tag() -> None:
    news_item = NewsItem(
        gid="1",
        title="Big news",
        date=datetime(2024, 5, 1, tzinfo=UTC),
        url="https://example.com/news",
        author="Dev",
        feedname="f",
        feedlabel="F",
        tags=["announcement"],
    )
    record = GameRecord(
        game=OwnedGame(appid=1, name="MyGame"),
        status=GameStatus(label="Sorti", badge="released", release_date="\u2014"),
    )
    row = make_news_row(record, news_item)
    assert 'data-tag="other"' in row
    assert "feed-tag-other" in row


def test_make_news_row_escapes_xss_in_title() -> None:
    news_item = NewsItem(
        gid="2",
        title="<script>alert('xss')</script>",
        date=datetime(2024, 5, 2, tzinfo=UTC),
        url="https://example.com/news2",
        author="Dev",
        feedname="f",
        feedlabel="F",
        tags=[],
    )
    record = GameRecord(
        game=OwnedGame(appid=1, name="Game"),
        status=GameStatus(label="Sorti", badge="released", release_date="\u2014"),
    )
    row = make_news_row(record, news_item)
    assert "<script>" not in row
    assert "&lt;script&gt;" in row


# ── generate_news_html ────────────────────────────────────────────────────────

def test_generate_news_html_replaces_all_placeholders(sample_record: GameRecord) -> None:
    page = generate_news_html([sample_record], "76561198000000000")
    for ph in ["__SHARED_JS__", "__GENERATED_AT__", "__STEAM_ID__", "__ROWS__", "__LIB_HREF__"]:
        assert ph not in page, f"Placeholder {ph} not replaced"


def test_generate_news_html_sorts_by_date_descending() -> None:
    older = NewsItem(
        gid="old", title="Old news", date=datetime(2024, 1, 1, tzinfo=UTC),
        url="https://example.com/old", author="A", feedname="f", feedlabel="F", tags=[],
    )
    newer = NewsItem(
        gid="new", title="Newest news", date=datetime(2024, 6, 1, tzinfo=UTC),
        url="https://example.com/new", author="A", feedname="f", feedlabel="F", tags=[],
    )
    record = GameRecord(
        game=OwnedGame(appid=1, name="SortGame"),
        status=GameStatus(label="Sorti", badge="released", release_date="\u2014"),
        news=[older, newer],
    )
    page = generate_news_html([record], "0")
    assert page.index("Newest news") < page.index("Old news")


# ── write_html / write_news_html ──────────────────────────────────────────────

def test_write_html_creates_file(sample_record: GameRecord, tmp_path: Path) -> None:
    out = tmp_path / "lib.html"
    write_html([sample_record], "76561198000000000", out)
    assert out.exists()
    assert "Half-Life 2" in out.read_text(encoding="utf-8")


def test_write_news_html_creates_file(sample_record: GameRecord, tmp_path: Path) -> None:
    out = tmp_path / "news.html"
    write_news_html([sample_record], "76561198000000000", out)
    assert out.exists()
    assert "Half-Life 2" in out.read_text(encoding="utf-8")

