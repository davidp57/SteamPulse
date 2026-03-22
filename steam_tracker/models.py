"""Domain models (Pydantic v2)."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# AppIDs >= this value are synthetic (hash-based) placeholders assigned to
# Epic games that could not be resolved to a real Steam AppID.  Real Steam
# AppIDs never exceed a few hundred million, so 2 billion is a safe sentinel.
SYNTHETIC_APPID_BASE: int = 2_000_000_000


class OwnedGame(BaseModel):
    appid: int
    name: str
    playtime_forever: int = 0
    playtime_2weeks: int = 0          # minutes played in the last 2 weeks
    rtime_last_played: int = 0        # unix timestamp of last play session
    img_icon_url: str = ""
    img_logo_url: str = ""
    source: str = "owned"             # "owned" | "wishlist" | "followed" | "epic"
    external_id: str = ""             # e.g. "epic:<catalogItemId>" for non-Steam games


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
    # Extended Store API fields
    dlc_appids: list[int] = Field(default_factory=list)
    controller_support: str = ""
    required_age: int = 0
    # SteamCMD fields (build / depot info)
    buildid: int = 0
    build_timeupdated: int = 0
    depot_size_bytes: int = 0
    branch_names: list[str] = Field(default_factory=list)


class SteamCmdInfo(BaseModel):
    """Build / depot information fetched from the SteamCMD API."""

    appid: int
    buildid: int = 0
    build_timeupdated: int = 0
    depot_size_bytes: int = 0
    branch_names: list[str] = Field(default_factory=list)


class FieldChange(BaseModel):
    """A single field change recorded for a game's ``app_details`` row."""

    appid: int
    field_name: str
    old_value: str | None
    new_value: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


class AlertRule(BaseModel):
    """A user-configured rule that produces alerts when matched."""

    name: str
    rule_type: Literal["news_keyword", "state_change"]
    icon: str = "📰"
    enabled: bool = True
    # news_keyword rule fields
    keywords: list[str] = Field(default_factory=list)
    match: Literal["title", "content", "any"] = "any"
    # state_change rule fields
    field: str = ""
    condition: Literal["changed", "increased", "decreased", "appeared", ""] = ""
    # Internal flag for the built-in "All News" rule
    builtin: bool = False


class Alert(BaseModel):
    """A triggered alert stored in the database."""

    id: str                                  # deterministic SHA-256 prefix
    rule_name: str
    rule_icon: str
    appid: int
    game_name: str = ""
    timestamp: datetime
    title: str
    details: str = ""
    url: str = ""
    source_type: str                         # "news" | "field_change"
    source_id: str = ""


class NewsItem(BaseModel):
    gid: str = ""                     # unique news item ID from Steam
    title: str
    date: datetime
    url: str
    author: str = ""
    contents: str = ""               # news body text (may be truncated)
    feedname: str = ""
    feedlabel: str = ""
    tags: list[str] = Field(default_factory=list)


class GameStatus(BaseModel):
    label: str
    badge: str  # "earlyaccess" | "released" | "unreleased" | "unknown"
    release_date: str


class SkippedItem(BaseModel):
    """An Epic library item that was skipped during discovery."""

    catalog_id: str
    raw_name: str
    reason: Literal[
        "no_title",
        "hex_id",
        "sandbox_label",
        "production_label",
        "duplicate",
    ]


class DiscoveryStats(BaseModel):
    """Statistics collected during Epic game discovery."""

    source: str = "epic"
    total_api_items: int = 0
    accepted_count: int = 0
    resolved_count: int = 0
    unresolved_count: int = 0
    skipped_items: list[SkippedItem] = Field(default_factory=list)


class GameRecord(BaseModel):
    game: OwnedGame
    details: AppDetails | None = None
    news: list[NewsItem] = Field(default_factory=list)
    status: GameStatus
    fetched_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=UTC)
    )
