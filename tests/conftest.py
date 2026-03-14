"""Shared pytest fixtures."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from steam_tracker.db import Database
from steam_tracker.models import AppDetails, GameRecord, GameStatus, NewsItem, OwnedGame


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    return Database(tmp_path / "test.db")


@pytest.fixture()
def sample_game() -> OwnedGame:
    return OwnedGame(
        appid=420,
        name="Half-Life 2",
        playtime_forever=3600,
        playtime_2weeks=120,
        rtime_last_played=1700000000,
    )


@pytest.fixture()
def sample_details() -> AppDetails:
    return AppDetails(
        appid=420,
        name="Half-Life 2",
        app_type="game",
        short_description="Gordon Freeman wakes up.",
        supported_languages="English, French",
        website="https://www.valvesoftware.com",
        header_image="https://cdn.akamai.steamstatic.com/steam/apps/420/header.jpg",
        background_image="https://cdn.akamai.steamstatic.com/steam/apps/420/page_bg.jpg",
        early_access=False,
        coming_soon=False,
        release_date_str="16 novembre 2004",
        developers=["Valve"],
        publishers=["Valve"],
        genres=["Action", "Shooter"],
        categories=["Single-player", "Steam Achievements"],
        is_free=False,
        price_initial=999,
        price_final=999,
        price_discount_pct=0,
        price_currency="EUR",
        platform_windows=True,
        platform_mac=True,
        platform_linux=True,
        metacritic_score=96,
        metacritic_url="https://www.metacritic.com/game/half-life-2",
        achievement_count=42,
        recommendation_count=300000,
    )


@pytest.fixture()
def sample_news() -> list[NewsItem]:
    return [
        NewsItem(
            gid="123456789",
            title="Update 1.0",
            date=datetime(2024, 1, 15, tzinfo=UTC),
            url="https://store.steampowered.com/news/app/420/view/1234",
            author="Valve",
            feedname="steam_community_announcements",
            feedlabel="Community Announcements",
            tags=["patchnotes", "valve"],
        ),
    ]


@pytest.fixture()
def sample_record(
    sample_game: OwnedGame,
    sample_details: AppDetails,
    sample_news: list[NewsItem],
) -> GameRecord:
    return GameRecord(
        game=sample_game,
        details=sample_details,
        news=sample_news,
        status=GameStatus(
            label="Sorti (1.0)", badge="released", release_date="16 novembre 2004"
        ),
    )
