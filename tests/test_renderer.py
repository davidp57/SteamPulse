"""Tests for steam_tracker.renderer."""
from __future__ import annotations

from steam_tracker.models import AppDetails, GameRecord, GameStatus, OwnedGame
from steam_tracker.renderer import (
    _metacritic_html,
    _platform_html,
    _price_html,
    format_playtime,
    generate_html,
    make_card,
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
    for ph in ["__GENERATED_AT__", "__STEAM_ID__", "__TOTAL__", "__EA__", "__REL__", "__UNREL__",
               "__CARDS__"]:
        assert ph not in page, f"Placeholder {ph} not replaced"


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
    assert "Gratuit" in _price_html(d)


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

