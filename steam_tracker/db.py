"""SQLite persistence layer."""
from __future__ import annotations

import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .models import AppDetails, GameRecord, GameStatus, NewsItem, OwnedGame

_DDL = """
CREATE TABLE IF NOT EXISTS games (
    appid            INTEGER PRIMARY KEY,
    name             TEXT    NOT NULL,
    playtime_forever INTEGER NOT NULL DEFAULT 0,
    playtime_2weeks  INTEGER NOT NULL DEFAULT 0,
    rtime_last_played INTEGER NOT NULL DEFAULT 0,
    img_icon_url     TEXT    NOT NULL DEFAULT '',
    img_logo_url     TEXT    NOT NULL DEFAULT '',
    last_seen_at     TEXT    NOT NULL,
    source           TEXT    NOT NULL DEFAULT 'owned',
    external_id      TEXT    NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS app_details (
    appid                INTEGER PRIMARY KEY REFERENCES games(appid) ON DELETE CASCADE,
    name                 TEXT    NOT NULL DEFAULT '',
    app_type             TEXT    NOT NULL DEFAULT '',
    short_description    TEXT    NOT NULL DEFAULT '',
    supported_languages  TEXT    NOT NULL DEFAULT '',
    website              TEXT    NOT NULL DEFAULT '',
    header_image         TEXT    NOT NULL DEFAULT '',
    background_image     TEXT    NOT NULL DEFAULT '',
    early_access         INTEGER NOT NULL DEFAULT 0,
    coming_soon          INTEGER NOT NULL DEFAULT 0,
    release_date_str     TEXT    NOT NULL DEFAULT '—',
    developers           TEXT    NOT NULL DEFAULT '[]',
    publishers           TEXT    NOT NULL DEFAULT '[]',
    genres               TEXT    NOT NULL DEFAULT '[]',
    categories           TEXT    NOT NULL DEFAULT '[]',
    is_free              INTEGER NOT NULL DEFAULT 0,
    price_initial        INTEGER NOT NULL DEFAULT 0,
    price_final          INTEGER NOT NULL DEFAULT 0,
    price_discount_pct   INTEGER NOT NULL DEFAULT 0,
    price_currency       TEXT    NOT NULL DEFAULT '',
    platform_windows     INTEGER NOT NULL DEFAULT 0,
    platform_mac         INTEGER NOT NULL DEFAULT 0,
    platform_linux       INTEGER NOT NULL DEFAULT 0,
    metacritic_score     INTEGER NOT NULL DEFAULT 0,
    metacritic_url       TEXT    NOT NULL DEFAULT '',
    achievement_count    INTEGER NOT NULL DEFAULT 0,
    recommendation_count INTEGER NOT NULL DEFAULT 0,
    fetched_at           TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS news (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    appid      INTEGER NOT NULL REFERENCES games(appid) ON DELETE CASCADE,
    gid        TEXT    NOT NULL DEFAULT '',
    title      TEXT    NOT NULL,
    date       TEXT    NOT NULL,
    url        TEXT    NOT NULL,
    author     TEXT    NOT NULL DEFAULT '',
    feedname   TEXT    NOT NULL DEFAULT '',
    feedlabel  TEXT    NOT NULL DEFAULT '',
    tags       TEXT    NOT NULL DEFAULT '[]',
    fetched_at TEXT    NOT NULL,
    UNIQUE (appid, url)
);

CREATE TABLE IF NOT EXISTS appid_mappings (
    external_source TEXT NOT NULL,
    external_id     TEXT NOT NULL,
    external_name   TEXT NOT NULL,
    steam_appid     INTEGER,
    resolved_at     TEXT NOT NULL,
    manual          INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (external_source, external_id)
);
"""

# Columns added after initial release — added via ALTER TABLE for existing DBs.
_MIGRATIONS: list[tuple[str, str, str]] = [
    # (table, column, column_definition)
    ("games", "playtime_2weeks", "INTEGER NOT NULL DEFAULT 0"),
    ("games", "rtime_last_played", "INTEGER NOT NULL DEFAULT 0"),
    ("app_details", "app_type", "TEXT NOT NULL DEFAULT ''"),
    ("app_details", "supported_languages", "TEXT NOT NULL DEFAULT ''"),
    ("app_details", "website", "TEXT NOT NULL DEFAULT ''"),
    ("app_details", "background_image", "TEXT NOT NULL DEFAULT ''"),
    ("app_details", "developers", "TEXT NOT NULL DEFAULT '[]'"),
    ("app_details", "publishers", "TEXT NOT NULL DEFAULT '[]'"),
    ("app_details", "genres", "TEXT NOT NULL DEFAULT '[]'"),
    ("app_details", "categories", "TEXT NOT NULL DEFAULT '[]'"),
    ("app_details", "is_free", "INTEGER NOT NULL DEFAULT 0"),
    ("app_details", "price_initial", "INTEGER NOT NULL DEFAULT 0"),
    ("app_details", "price_final", "INTEGER NOT NULL DEFAULT 0"),
    ("app_details", "price_discount_pct", "INTEGER NOT NULL DEFAULT 0"),
    ("app_details", "price_currency", "TEXT NOT NULL DEFAULT ''"),
    ("app_details", "platform_windows", "INTEGER NOT NULL DEFAULT 0"),
    ("app_details", "platform_mac", "INTEGER NOT NULL DEFAULT 0"),
    ("app_details", "platform_linux", "INTEGER NOT NULL DEFAULT 0"),
    ("app_details", "metacritic_score", "INTEGER NOT NULL DEFAULT 0"),
    ("app_details", "metacritic_url", "TEXT NOT NULL DEFAULT ''"),
    ("app_details", "achievement_count", "INTEGER NOT NULL DEFAULT 0"),
    ("app_details", "recommendation_count", "INTEGER NOT NULL DEFAULT 0"),
    ("news", "gid", "TEXT NOT NULL DEFAULT ''"),
    ("news", "author", "TEXT NOT NULL DEFAULT ''"),
    ("news", "feedlabel", "TEXT NOT NULL DEFAULT ''"),
    ("news", "tags", "TEXT NOT NULL DEFAULT '[]'"),
    ("games", "source", "TEXT NOT NULL DEFAULT 'owned'"),
    ("games", "details_fetched_at", "TEXT"),
    ("games", "news_fetched_at", "TEXT"),
    ("games", "external_id", "TEXT NOT NULL DEFAULT ''"),
]


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def infer_status(details: AppDetails | None) -> GameStatus:
    """Pure function: derive a GameStatus from optional AppDetails."""
    if details is None:
        return GameStatus(label="Inconnu", badge="unknown", release_date="—")
    if details.coming_soon:
        return GameStatus(
            label="Pas encore sorti",
            badge="unreleased",
            release_date=details.release_date_str,
        )
    if details.early_access:
        return GameStatus(
            label="Early Access",
            badge="earlyaccess",
            release_date=details.release_date_str,
        )
    return GameStatus(
        label="Sorti (1.0)",
        badge="released",
        release_date=details.release_date_str,
    )


class Database:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._init_schema()

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        con = sqlite3.connect(self._path)
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA foreign_keys=ON")
        try:
            yield con
            con.commit()
        finally:
            con.close()

    def _init_schema(self) -> None:
        with self._connect() as con:
            con.executescript(_DDL)
            # Apply additive migrations for pre-existing databases.
            existing: dict[str, set[str]] = {}
            for table, col, col_def in _MIGRATIONS:
                if table not in existing:
                    rows = con.execute(f"PRAGMA table_info({table})").fetchall()  # noqa: S608
                    existing[table] = {str(r[1]) for r in rows}
                if col not in existing[table]:
                    con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")  # noqa: S608
                    existing[table].add(col)

    def upsert_game(self, game: OwnedGame) -> None:
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO games
                    (appid, name, playtime_forever, playtime_2weeks,
                     rtime_last_played, img_icon_url, img_logo_url, last_seen_at, source,
                     external_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(appid) DO UPDATE SET
                    name = CASE WHEN excluded.name != ''
                        THEN excluded.name ELSE name END,
                    playtime_forever = CASE WHEN excluded.source = 'owned'
                        THEN excluded.playtime_forever ELSE playtime_forever END,
                    playtime_2weeks = CASE WHEN excluded.source = 'owned'
                        THEN excluded.playtime_2weeks ELSE playtime_2weeks END,
                    rtime_last_played = CASE WHEN excluded.source = 'owned'
                        THEN excluded.rtime_last_played ELSE rtime_last_played END,
                    img_icon_url = CASE WHEN excluded.img_icon_url != ''
                        THEN excluded.img_icon_url ELSE img_icon_url END,
                    img_logo_url = CASE WHEN excluded.img_logo_url != ''
                        THEN excluded.img_logo_url ELSE img_logo_url END,
                    source = CASE
                        WHEN source = 'owned'          THEN 'owned'
                        WHEN excluded.source = 'owned' THEN 'owned'
                        WHEN source = 'epic'           THEN 'epic'
                        WHEN excluded.source = 'epic'  THEN 'epic'
                        WHEN source = 'wishlist'          THEN 'wishlist'
                        WHEN excluded.source = 'wishlist' THEN 'wishlist'
                        ELSE excluded.source
                    END,
                    external_id = CASE WHEN excluded.external_id != ''
                        THEN excluded.external_id ELSE external_id END,
                    last_seen_at = excluded.last_seen_at
                """,
                (
                    game.appid,
                    game.name,
                    game.playtime_forever,
                    game.playtime_2weeks,
                    game.rtime_last_played,
                    game.img_icon_url,
                    game.img_logo_url,
                    _now(),
                    game.source,
                    game.external_id,
                ),
            )

    def upsert_app_details(self, details: AppDetails) -> None:
        with self._connect() as con:
            # Back-fill games.name for followed/wishlist games that arrived without one
            if details.name:
                con.execute(
                    "UPDATE games SET name = ? WHERE appid = ? AND name = ''",
                    (details.name, details.appid),
                )
            con.execute(
                """
                INSERT INTO app_details
                    (appid, name, app_type, short_description, supported_languages,
                     website, header_image, background_image,
                     early_access, coming_soon, release_date_str,
                     developers, publishers, genres, categories,
                     is_free, price_initial, price_final, price_discount_pct, price_currency,
                     platform_windows, platform_mac, platform_linux,
                     metacritic_score, metacritic_url,
                     achievement_count, recommendation_count,
                     fetched_at)
                VALUES (?,?,?,?,?, ?,?,?, ?,?,?, ?,?,?,?, ?,?,?,?,?, ?,?,?, ?,?, ?,?, ?)
                ON CONFLICT(appid) DO UPDATE SET
                    name                 = excluded.name,
                    app_type             = excluded.app_type,
                    short_description    = excluded.short_description,
                    supported_languages  = excluded.supported_languages,
                    website              = excluded.website,
                    header_image         = excluded.header_image,
                    background_image     = excluded.background_image,
                    early_access         = excluded.early_access,
                    coming_soon          = excluded.coming_soon,
                    release_date_str     = excluded.release_date_str,
                    developers           = excluded.developers,
                    publishers           = excluded.publishers,
                    genres               = excluded.genres,
                    categories           = excluded.categories,
                    is_free              = excluded.is_free,
                    price_initial        = excluded.price_initial,
                    price_final          = excluded.price_final,
                    price_discount_pct   = excluded.price_discount_pct,
                    price_currency       = excluded.price_currency,
                    platform_windows     = excluded.platform_windows,
                    platform_mac         = excluded.platform_mac,
                    platform_linux       = excluded.platform_linux,
                    metacritic_score     = excluded.metacritic_score,
                    metacritic_url       = excluded.metacritic_url,
                    achievement_count    = excluded.achievement_count,
                    recommendation_count = excluded.recommendation_count,
                    fetched_at           = excluded.fetched_at
                """,
                (
                    details.appid,
                    details.name,
                    details.app_type,
                    details.short_description,
                    details.supported_languages,
                    details.website,
                    details.header_image,
                    details.background_image,
                    int(details.early_access),
                    int(details.coming_soon),
                    details.release_date_str,
                    json.dumps(details.developers),
                    json.dumps(details.publishers),
                    json.dumps(details.genres),
                    json.dumps(details.categories),
                    int(details.is_free),
                    details.price_initial,
                    details.price_final,
                    details.price_discount_pct,
                    details.price_currency,
                    int(details.platform_windows),
                    int(details.platform_mac),
                    int(details.platform_linux),
                    details.metacritic_score,
                    details.metacritic_url,
                    details.achievement_count,
                    details.recommendation_count,
                    _now(),
                ),
            )

    def mark_fetched(
        self, appids: set[int], *, details: bool = False, news: bool = False
    ) -> None:
        """Record that a fetch was attempted for *appids*, even if it returned nothing.

        Pass ``details=True`` to update ``details_fetched_at`` (suppresses
        constant retries for apps the Store API doesn't serve, e.g. DLCs).
        Pass ``news=True`` to update ``news_fetched_at`` (prevents games with
        zero or unchanged news from being re-fetched every run via INSERT OR IGNORE).
        """
        if not appids:
            return
        cols: list[str] = []
        if details:
            cols.append("details_fetched_at")
        if news:
            cols.append("news_fetched_at")
        if not cols:
            return
        now = _now()
        set_clause = ", ".join(f"{c} = ?" for c in cols)
        vals = [now] * len(cols)
        with self._connect() as con:
            con.executemany(
                f"UPDATE games SET {set_clause} WHERE appid = ?",  # noqa: S608
                [[*vals, appid] for appid in appids],
            )

    def upsert_news(self, appid: int, news: list[NewsItem]) -> None:
        now = _now()
        with self._connect() as con:
            for item in news:
                con.execute(
                    """
                    INSERT OR IGNORE INTO news
                        (appid, gid, title, date, url,
                         author, feedname, feedlabel, tags, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        appid,
                        item.gid,
                        item.title,
                        item.date.isoformat(),
                        item.url,
                        item.author,
                        item.feedname,
                        item.feedlabel,
                        json.dumps(item.tags),
                        now,
                    ),
                )

    def get_cached_appids(self) -> set[int]:
        """Return appids that either have app_details or were attempted recently (7-day TTL)."""
        threshold = (datetime.now(UTC) - timedelta(days=7)).isoformat()
        with self._connect() as con:
            rows = con.execute(
                """
                SELECT appid FROM app_details
                UNION
                SELECT appid FROM games
                WHERE details_fetched_at IS NOT NULL AND details_fetched_at > ?
                """,
                (threshold,),
            ).fetchall()
        return {int(r[0]) for r in rows}

    def get_stale_news_appids(self, max_age_seconds: int) -> set[int]:
        """Return appids whose news has not been fetched within *max_age_seconds*.

        Checks both the last news inserted and the explicit ``news_fetched_at``
        marker so that games with zero news (INSERT OR IGNORE no-ops) are
        correctly handled.
        """
        threshold = (datetime.now(UTC) - timedelta(seconds=max_age_seconds)).isoformat()
        with self._connect() as con:
            rows = con.execute(
                """
                SELECT g.appid FROM games g
                LEFT JOIN (
                    SELECT appid, MAX(fetched_at) AS last_fetch FROM news GROUP BY appid
                ) n ON g.appid = n.appid
                WHERE (n.last_fetch IS NULL OR n.last_fetch < ?)
                  AND (g.news_fetched_at IS NULL OR g.news_fetched_at < ?)
                """,
                (threshold, threshold),
            ).fetchall()
        return {int(r[0]) for r in rows}

    def get_all_game_records(self) -> list[GameRecord]:
        """Return all games with their details and latest news, sorted by name."""
        with self._connect() as con:
            games_rows = con.execute(
                "SELECT appid, name, playtime_forever, playtime_2weeks, "
                "rtime_last_played, img_icon_url, img_logo_url, source, external_id "
                "FROM games ORDER BY name COLLATE NOCASE"
            ).fetchall()

            records: list[GameRecord] = []
            for row in games_rows:
                appid: int = int(row[0])
                game = OwnedGame(
                    appid=appid,
                    name=str(row[1]),
                    playtime_forever=int(row[2]),
                    playtime_2weeks=int(row[3]),
                    rtime_last_played=int(row[4]),
                    img_icon_url=str(row[5]),
                    img_logo_url=str(row[6]),
                    source=str(row[7]),
                    external_id=str(row[8]),
                )

                det = con.execute(
                    "SELECT name, app_type, short_description, supported_languages, "
                    "website, header_image, background_image, "
                    "early_access, coming_soon, release_date_str, "
                    "developers, publishers, genres, categories, "
                    "is_free, price_initial, price_final, price_discount_pct, price_currency, "
                    "platform_windows, platform_mac, platform_linux, "
                    "metacritic_score, metacritic_url, achievement_count, recommendation_count "
                    "FROM app_details WHERE appid = ?",
                    (appid,),
                ).fetchone()

                details: AppDetails | None = None
                if det is not None:
                    details = AppDetails(
                        appid=appid,
                        name=str(det[0]),
                        app_type=str(det[1]),
                        short_description=str(det[2]),
                        supported_languages=str(det[3]),
                        website=str(det[4]),
                        header_image=str(det[5]),
                        background_image=str(det[6]),
                        early_access=bool(det[7]),
                        coming_soon=bool(det[8]),
                        release_date_str=str(det[9]),
                        developers=json.loads(str(det[10])),
                        publishers=json.loads(str(det[11])),
                        genres=json.loads(str(det[12])),
                        categories=json.loads(str(det[13])),
                        is_free=bool(det[14]),
                        price_initial=int(det[15]),
                        price_final=int(det[16]),
                        price_discount_pct=int(det[17]),
                        price_currency=str(det[18]),
                        platform_windows=bool(det[19]),
                        platform_mac=bool(det[20]),
                        platform_linux=bool(det[21]),
                        metacritic_score=int(det[22]),
                        metacritic_url=str(det[23]),
                        achievement_count=int(det[24]),
                        recommendation_count=int(det[25]),
                    )

                news_rows = con.execute(
                    "SELECT gid, title, date, url, author, feedname, feedlabel, tags "
                    "FROM news WHERE appid = ? ORDER BY date DESC LIMIT 5",
                    (appid,),
                ).fetchall()
                news = [
                    NewsItem(
                        gid=str(r[0]),
                        title=str(r[1]),
                        date=datetime.fromisoformat(str(r[2])),
                        url=str(r[3]),
                        author=str(r[4]),
                        feedname=str(r[5]),
                        feedlabel=str(r[6]),
                        tags=json.loads(str(r[7])),
                    )
                    for r in news_rows
                ]

                records.append(
                    GameRecord(game=game, details=details, news=news, status=infer_status(details))
                )

        return records

    def get_appid_mapping(self, source: str, external_id: str) -> int | None:
        """Return the cached Steam AppID for an external game, or None."""
        with self._connect() as con:
            row = con.execute(
                "SELECT steam_appid FROM appid_mappings "
                "WHERE external_source = ? AND external_id = ?",
                (source, external_id),
            ).fetchone()
        if row is None or row[0] is None:
            return None
        return int(row[0])

    def upsert_appid_mapping(
        self,
        source: str,
        external_id: str,
        name: str,
        steam_appid: int | None,
        *,
        manual: bool = False,
    ) -> None:
        """Insert or update an AppID mapping.

        Manual mappings (``manual=True``) are never overwritten by automatic
        resolution.
        """
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO appid_mappings
                    (external_source, external_id, external_name,
                     steam_appid, resolved_at, manual)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(external_source, external_id) DO UPDATE SET
                    external_name = excluded.external_name,
                    steam_appid   = CASE
                        WHEN appid_mappings.manual = 1 AND excluded.manual = 0
                            THEN appid_mappings.steam_appid
                        ELSE excluded.steam_appid
                    END,
                    resolved_at   = excluded.resolved_at,
                    manual        = CASE
                        WHEN appid_mappings.manual = 1 AND excluded.manual = 0
                            THEN appid_mappings.manual
                        ELSE excluded.manual
                    END
                """,
                (source, external_id, name, steam_appid, _now(), int(manual)),
            )
