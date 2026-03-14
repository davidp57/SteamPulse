"""Domain models (Pydantic v2)."""
from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class OwnedGame(BaseModel):
    appid: int
    name: str
    playtime_forever: int = 0
    playtime_2weeks: int = 0          # minutes played in the last 2 weeks
    rtime_last_played: int = 0        # unix timestamp of last play session
    img_icon_url: str = ""
    img_logo_url: str = ""
    source: str = "owned"             # "owned" | "wishlist" | "followed"


class AppDetails(BaseModel):
    appid: int
    # Identity
    name: str = ""
    app_type: str = ""                # "game" | "dlc" | "demo" | "mod" | …
    # Descriptions
    short_description: str = ""
    supported_languages: str = ""
    website: str = ""
    # Images
    header_image: str = ""
    background_image: str = ""
    # Release
    early_access: bool = False
    coming_soon: bool = False
    release_date_str: str = "—"
    # Developers / Publishers
    developers: list[str] = Field(default_factory=list)
    publishers: list[str] = Field(default_factory=list)
    # Taxonomy
    genres: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    # Business
    is_free: bool = False
    price_initial: int = 0            # in cents (store currency)
    price_final: int = 0              # after discount
    price_discount_pct: int = 0
    price_currency: str = ""
    # Platforms
    platform_windows: bool = False
    platform_mac: bool = False
    platform_linux: bool = False
    # Quality signals
    metacritic_score: int = 0
    metacritic_url: str = ""
    achievement_count: int = 0
    recommendation_count: int = 0


class NewsItem(BaseModel):
    gid: str = ""                     # unique news item ID from Steam
    title: str
    date: datetime
    url: str
    author: str = ""
    feedname: str = ""
    feedlabel: str = ""
    tags: list[str] = Field(default_factory=list)


class GameStatus(BaseModel):
    label: str
    badge: str  # "earlyaccess" | "released" | "unreleased" | "unknown"
    release_date: str


class GameRecord(BaseModel):
    game: OwnedGame
    details: AppDetails | None = None
    news: list[NewsItem] = Field(default_factory=list)
    status: GameStatus
    fetched_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=UTC)
    )
