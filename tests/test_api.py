"""Tests for steam_tracker.api."""
from __future__ import annotations

import responses as resp_mock

from steam_tracker.api import get_app_details, get_app_news, get_owned_games
from steam_tracker.models import AppDetails, NewsItem, OwnedGame

_STEAM_API = "https://api.steampowered.com"
_STORE_API = "https://store.steampowered.com/api"

_FULL_APP_DATA = {
    "name": "Half-Life 2",
    "type": "game",
    "short_description": "Gordon Freeman wakes up.",
    "supported_languages": "English, French",
    "website": "https://www.valvesoftware.com",
    "header_image": "https://example.com/header.jpg",
    "background": "https://example.com/bg.jpg",
    "early_access": False,
    "categories": [{"description": "Single-player"}, {"description": "Steam Achievements"}],
    "genres": [{"description": "Action"}, {"description": "Shooter"}],
    "developers": ["Valve"],
    "publishers": ["Valve"],
    "is_free": False,
    "price_overview": {
        "currency": "EUR",
        "initial": 999,
        "final": 499,
        "discount_percent": 50,
    },
    "platforms": {"windows": True, "mac": True, "linux": True},
    "metacritic": {"score": 96, "url": "https://www.metacritic.com/game/half-life-2"},
    "achievements": {"total": 42},
    "recommendations": {"total": 300000},
    "release_date": {"coming_soon": False, "date": "16 Nov, 2004"},
}


@resp_mock.activate
def test_get_owned_games_returns_list() -> None:
    resp_mock.add(
        resp_mock.GET,
        f"{_STEAM_API}/IPlayerService/GetOwnedGames/v1/",
        json={
            "response": {
                "games": [
                    {
                        "appid": 420,
                        "name": "Half-Life 2",
                        "playtime_forever": 100,
                        "playtime_2weeks": 30,
                        "rtime_last_played": 1700000000,
                    },
                    {"appid": 730, "name": "CS2", "playtime_forever": 5000},
                ]
            }
        },
    )
    games = get_owned_games("fake_key", "76561198000000000")
    assert len(games) == 2
    assert isinstance(games[0], OwnedGame)
    assert games[0].appid == 420
    assert games[0].playtime_2weeks == 30
    assert games[0].rtime_last_played == 1700000000
    assert games[1].name == "CS2"


@resp_mock.activate
def test_get_owned_games_empty_library() -> None:
    resp_mock.add(
        resp_mock.GET,
        f"{_STEAM_API}/IPlayerService/GetOwnedGames/v1/",
        json={"response": {}},
    )
    assert get_owned_games("fake_key", "76561198000000000") == []


@resp_mock.activate
def test_get_app_details_released() -> None:
    resp_mock.add(
        resp_mock.GET,
        f"{_STORE_API}/appdetails",
        json={"420": {"success": True, "data": _FULL_APP_DATA}},
    )
    details = get_app_details(420)
    assert isinstance(details, AppDetails)
    assert details.early_access is False
    assert details.coming_soon is False
    assert details.release_date_str == "16 Nov, 2004"


@resp_mock.activate
def test_get_app_details_extracts_all_new_fields() -> None:
    resp_mock.add(
        resp_mock.GET,
        f"{_STORE_API}/appdetails",
        json={"420": {"success": True, "data": _FULL_APP_DATA}},
    )
    d = get_app_details(420)
    assert d is not None
    assert d.app_type == "game"
    assert d.developers == ["Valve"]
    assert d.publishers == ["Valve"]
    assert d.genres == ["Action", "Shooter"]
    assert d.categories == ["Single-player", "Steam Achievements"]
    assert d.is_free is False
    assert d.price_initial == 999
    assert d.price_final == 499
    assert d.price_discount_pct == 50
    assert d.price_currency == "EUR"
    assert d.platform_windows is True
    assert d.platform_mac is True
    assert d.platform_linux is True
    assert d.metacritic_score == 96
    assert d.metacritic_url == "https://www.metacritic.com/game/half-life-2"
    assert d.achievement_count == 42
    assert d.recommendation_count == 300000
    assert d.supported_languages == "English, French"
    assert d.website == "https://www.valvesoftware.com"


@resp_mock.activate
def test_get_app_details_early_access_via_flag() -> None:
    """French locale category text 'Accès anticipé' is also detected."""
    resp_mock.add(
        resp_mock.GET,
        f"{_STORE_API}/appdetails",
        json={
            "999": {
                "success": True,
                "data": {
                    "name": "EA Game",
                    "genres": [],
                    "categories": [{"description": "Accès anticipé"}],
                    "release_date": {"coming_soon": False, "date": "2023"},
                    "short_description": "",
                    "header_image": "",
                },
            }
        },
    )
    details = get_app_details(999)
    assert details is not None
    assert details.early_access is True


@resp_mock.activate
def test_get_app_details_early_access_via_category() -> None:
    resp_mock.add(
        resp_mock.GET,
        f"{_STORE_API}/appdetails",
        json={
            "888": {
                "success": True,
                "data": {
                    "name": "EA via category",
                    "categories": [{"description": "Early Access"}],
                    "release_date": {"coming_soon": False, "date": "2024"},
                    "short_description": "",
                    "header_image": "",
                },
            }
        },
    )
    details = get_app_details(888)
    assert details is not None
    assert details.early_access is True


@resp_mock.activate
def test_get_app_details_early_access_via_genre_id() -> None:
    """Genre ID 70 = Early Access, language-independent (French API locale)."""
    resp_mock.add(
        resp_mock.GET,
        f"{_STORE_API}/appdetails",
        json={
            "777": {
                "success": True,
                "data": {
                    "name": "EA via genre id",
                    "genres": [{"id": "70", "description": "Accès anticipé"}],
                    "categories": [],
                    "release_date": {"coming_soon": False, "date": "2025"},
                    "short_description": "",
                    "header_image": "",
                },
            }
        },
    )
    details = get_app_details(777)
    assert details is not None
    assert details.early_access is True


@resp_mock.activate
def test_get_app_details_free_game_no_price() -> None:
    resp_mock.add(
        resp_mock.GET,
        f"{_STORE_API}/appdetails",
        json={
            "570": {
                "success": True,
                "data": {
                    "name": "Dota 2",
                    "is_free": True,
                    "categories": [],
                    "release_date": {"coming_soon": False, "date": "2013"},
                    "short_description": "",
                    "header_image": "",
                },
            }
        },
    )
    d = get_app_details(570)
    assert d is not None
    assert d.is_free is True
    assert d.price_initial == 0
    assert d.price_currency == ""


@resp_mock.activate
def test_get_app_details_returns_none_on_api_failure() -> None:
    resp_mock.add(
        resp_mock.GET,
        f"{_STORE_API}/appdetails",
        json={"123": {"success": False}},
    )
    assert get_app_details(123) is None


@resp_mock.activate
def test_get_app_details_returns_none_on_http_error() -> None:
    resp_mock.add(resp_mock.GET, f"{_STORE_API}/appdetails", status=500)
    assert get_app_details(42) is None


@resp_mock.activate
def test_get_app_news_returns_items() -> None:
    resp_mock.add(
        resp_mock.GET,
        f"{_STEAM_API}/ISteamNews/GetNewsForApp/v2/",
        json={
            "appnews": {
                "newsitems": [
                    {
                        "gid": "987654",
                        "title": "Patch 1.5",
                        "date": 1700000000,
                        "url": "https://store.steampowered.com/news/420/1",
                        "author": "ValveBot",
                        "feedname": "steam_community_announcements",
                        "feedlabel": "Community Announcements",
                        "tags": "patchnotes,valve",
                    }
                ]
            }
        },
    )
    news = get_app_news(420, count=1)
    assert len(news) == 1
    assert isinstance(news[0], NewsItem)
    assert news[0].title == "Patch 1.5"
    assert news[0].gid == "987654"
    assert news[0].author == "ValveBot"
    assert news[0].feedlabel == "Community Announcements"
    assert news[0].tags == ["patchnotes", "valve"]


@resp_mock.activate
def test_get_app_news_returns_empty_on_error() -> None:
    resp_mock.add(resp_mock.GET, f"{_STEAM_API}/ISteamNews/GetNewsForApp/v2/", status=429)
    assert get_app_news(420) == []

