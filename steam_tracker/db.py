"""SQLite persistence layer."""
from __future__ import annotations

import json
import logging
import re
import sqlite3
from collections.abc import Callable, Generator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .models import Alert, AppDetails, FieldChange, GameRecord, GameStatus, NewsItem, OwnedGame

log = logging.getLogger(__name__)

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

CREATE TABLE IF NOT EXISTS field_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    appid      INTEGER NOT NULL,
    field_name TEXT    NOT NULL,
    old_value  TEXT,
    new_value  TEXT    NOT NULL,
    timestamp  TEXT    NOT NULL,
    FOREIGN KEY (appid) REFERENCES games(appid) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_fh_appid ON field_history(appid);
CREATE INDEX IF NOT EXISTS idx_fh_field ON field_history(field_name);
CREATE INDEX IF NOT EXISTS idx_fh_ts    ON field_history(timestamp);

CREATE TABLE IF NOT EXISTS alerts (
    id          TEXT    PRIMARY KEY,
    rule_name   TEXT    NOT NULL,
    rule_icon   TEXT    NOT NULL DEFAULT '📰',
    appid       INTEGER NOT NULL,
    timestamp   TEXT    NOT NULL,
    title       TEXT    NOT NULL,
    details     TEXT    NOT NULL DEFAULT '',
    url         TEXT    NOT NULL DEFAULT '',
    source_type TEXT    NOT NULL,
    source_id   TEXT    NOT NULL DEFAULT '',
    FOREIGN KEY (appid) REFERENCES games(appid) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_alerts_rule ON alerts(rule_name);
CREATE INDEX IF NOT EXISTS idx_alerts_appid ON alerts(appid);
CREATE INDEX IF NOT EXISTS idx_alerts_ts    ON alerts(timestamp);
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
    # Extended app_details columns (added in v1.3.0)
    ("app_details", "dlc_appids", "TEXT NOT NULL DEFAULT '[]'"),
    ("app_details", "controller_support", "TEXT NOT NULL DEFAULT ''"),
    ("app_details", "required_age", "INTEGER NOT NULL DEFAULT 0"),
    ("app_details", "buildid", "INTEGER NOT NULL DEFAULT 0"),
    ("app_details", "build_timeupdated", "INTEGER NOT NULL DEFAULT 0"),
    ("app_details", "depot_size_bytes", "INTEGER NOT NULL DEFAULT 0"),
    ("app_details", "branch_names", "TEXT NOT NULL DEFAULT '[]'"),
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

    # ── Data cleanup ──────────────────────────────────────────────────────

    def run_cleanup(self) -> int:
        """Run all data-cleanup rules and return the number of primary entries cleaned.

        Each rule is a private method named ``_cleanup_*``.  New rules should
        be added to the ``_CLEANUP_RULES`` list below.

        Note:
            The returned count reflects the number of primary rows (e.g. games)
            cleaned.  Related rows (e.g. ``appid_mappings``) may also be
            deleted but are not included in the count.

        Returns:
            Total number of primary entries deleted or corrected across all rules.
        """
        total = 0
        for rule in self._CLEANUP_RULES:
            total += rule(self)
        return total

    def _cleanup_epic_live_name(self) -> int:
        """Remove Epic games named 'Live' (incorrect sandboxName) and their mappings.

        These entries were created by a bug that used the sandbox environment
        label instead of the real game title.  Removing them forces a clean
        re-discovery on the next fetch.

        Returns:
            Number of games deleted.
        """
        with self._connect() as con:
            rows = con.execute(
                "SELECT appid, external_id FROM games "
                "WHERE source = 'epic' AND name = 'Live'",
            ).fetchall()
            if not rows:
                return 0
            appids = [int(r[0]) for r in rows]
            ext_ids = [str(r[1]) for r in rows if r[1]]
            # Delete games (cascades to app_details, news, alerts, field_history)
            con.executemany("DELETE FROM games WHERE appid = ?", [(a,) for a in appids])
            # Invalidate cached appid_mappings so the resolver retries
            if ext_ids:
                con.executemany(
                    "DELETE FROM appid_mappings "
                    "WHERE external_source = 'epic' AND external_id = ?",
                    [(e,) for e in ext_ids],
                )
            log.info("cleanup: removed %d Epic game(s) named 'Live'", len(appids))
            return len(appids)

    # Pattern matching hex-like identifiers (24+ lowercase hex chars).
    _HEX_ID_RE = re.compile(r"^[a-f0-9]{24,}$")

    def _cleanup_epic_hex_id_name(self) -> int:
        """Remove Epic games whose name is a raw hex catalog identifier.

        These entries were imported before hex-ID filtering was added.
        Removing them forces a clean re-discovery on the next fetch.

        Returns:
            Number of games deleted.
        """
        with self._connect() as con:
            rows = con.execute(
                "SELECT appid, name, external_id FROM games WHERE source = 'epic'",
            ).fetchall()
            hex_rows = [(int(r[0]), str(r[2])) for r in rows if self._HEX_ID_RE.match(str(r[1]))]
            if not hex_rows:
                return 0
            appids = [a for a, _ in hex_rows]
            ext_ids = [e for _, e in hex_rows if e]
            con.executemany("DELETE FROM games WHERE appid = ?", [(a,) for a in appids])
            if ext_ids:
                con.executemany(
                    "DELETE FROM appid_mappings "
                    "WHERE external_source = 'epic' AND external_id = ?",
                    [(e,) for e in ext_ids],
                )
            log.info("cleanup: removed %d Epic game(s) with hex-ID names", len(appids))
            return len(appids)

    # Pattern matching Epic sandbox deployment names (e.g. "ashishim Production").
    _PRODUCTION_NAME_RE = re.compile(r"^\w+ Production$")

    def _cleanup_epic_production_name(self) -> int:
        """Remove Epic games whose name matches '<word> Production'.

        These entries correspond to Epic sandbox deployment environment
        labels (e.g. 'ashishim Production', 'blackcoral Production') that
        were incorrectly stored as game titles.  Removing them forces a
        clean re-discovery on the next fetch.

        Returns:
            Number of games deleted.
        """
        with self._connect() as con:
            rows = con.execute(
                "SELECT appid, name, external_id FROM games WHERE source = 'epic'",
            ).fetchall()
            prod_rows = [
                (int(r[0]), str(r[2]))
                for r in rows
                if self._PRODUCTION_NAME_RE.match(str(r[1]))
            ]
            if not prod_rows:
                return 0
            appids = [a for a, _ in prod_rows]
            ext_ids = [e for _, e in prod_rows if e]
            con.executemany("DELETE FROM games WHERE appid = ?", [(a,) for a in appids])
            if ext_ids:
                con.executemany(
                    "DELETE FROM appid_mappings "
                    "WHERE external_source = 'epic' AND external_id = ?",
                    [(e,) for e in ext_ids],
                )
            log.info("cleanup: removed %d Epic game(s) with Production names", len(appids))
            return len(appids)

    def _cleanup_epic_duplicate_external_id(self) -> int:
        """Remove synthetic-appid duplicates when a real-appid entry exists.

        When an Epic game was imported multiple times (once with a real
        Steam AppID < 2 000 000 000 and once with a synthetic AppID),
        the synthetic duplicate is redundant.  This rule keeps only the
        entry with the smallest AppID and deletes the rest.

        Also handles cross-source duplicates: e.g. a game with source='owned'
        (real appid) and source='epic' (synthetic appid) sharing the same
        external_id.

        Returns:
            Number of games deleted.
        """
        with self._connect() as con:
            # Find synthetic-appid rows whose external_id also appears on a
            # real-appid row (regardless of source).
            dup_rows = con.execute(
                "SELECT g2.appid, g2.external_id FROM games g2 "
                "WHERE g2.appid >= 2000000000 "
                "AND g2.external_id IS NOT NULL "
                "AND g2.external_id != '' "
                "AND g2.external_id IN ("
                "  SELECT g1.external_id FROM games g1 "
                "  WHERE g1.appid < 2000000000"
                ")",
            ).fetchall()
            if not dup_rows:
                return 0
            appids = [int(r[0]) for r in dup_rows]
            ext_ids = [str(r[1]) for r in dup_rows if r[1]]
            con.executemany("DELETE FROM games WHERE appid = ?", [(a,) for a in appids])
            if ext_ids:
                con.executemany(
                    "DELETE FROM appid_mappings "
                    "WHERE external_source = 'epic' AND external_id = ?",
                    [(e,) for e in ext_ids],
                )
            log.info(
                "cleanup: removed %d Epic synthetic-appid duplicate(s)", len(appids),
            )
            return len(appids)

    def _cleanup_epic_duplicate_name(self) -> int:
        """Remove synthetic-appid duplicates when a real-appid entry shares the same name.

        When an Epic game appears multiple times with different external_ids
        but the same display name (e.g. Death Stranding ×5), only the entry
        with the lowest appid (the real one) should be kept.

        Returns:
            Number of games deleted.
        """
        with self._connect() as con:
            dup_rows = con.execute(
                "SELECT g2.appid, g2.external_id FROM games g2 "
                "WHERE g2.appid >= 2000000000 "
                "AND g2.name IN ("
                "  SELECT g1.name FROM games g1 "
                "  WHERE g1.appid < 2000000000 AND g1.name != ''"
                ")",
            ).fetchall()
            if not dup_rows:
                return 0
            appids = [int(r[0]) for r in dup_rows]
            ext_ids = [str(r[1]) for r in dup_rows if r[1]]
            con.executemany("DELETE FROM games WHERE appid = ?", [(a,) for a in appids])
            if ext_ids:
                con.executemany(
                    "DELETE FROM appid_mappings "
                    "WHERE external_source = 'epic' AND external_id = ?",
                    [(e,) for e in ext_ids],
                )
            log.info(
                "cleanup: removed %d Epic same-name duplicate(s)", len(appids),
            )
            return len(appids)

    _CLEANUP_RULES: list[Callable[[Database], int]] = [
        _cleanup_epic_live_name,
        _cleanup_epic_hex_id_name,
        _cleanup_epic_production_name,
        _cleanup_epic_duplicate_external_id,
        _cleanup_epic_duplicate_name,
    ]

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

    def upsert_app_details(self, details: AppDetails) -> list[FieldChange]:
        """Insert or update app details and return a list of changed fields.

        Computes a diff against the previously stored row so that callers
        can pass the returned :class:`~steam_tracker.models.FieldChange`
        objects to the alert engine.

        Args:
            details: The new :class:`~steam_tracker.models.AppDetails` to persist.

        Returns:
            List of :class:`~steam_tracker.models.FieldChange` objects for
            every field whose value changed (empty on first insert).
        """
        now = _now()
        with self._connect() as con:
            # Back-fill games.name for followed/wishlist games that arrived without one
            if details.name:
                con.execute(
                    "UPDATE games SET name = ? WHERE appid = ? AND name = ''",
                    (details.name, details.appid),
                )

            # Read the old row to compute a diff
            old_row = con.execute(
                "SELECT name, app_type, short_description, supported_languages, "
                "website, header_image, background_image, "
                "early_access, coming_soon, release_date_str, "
                "developers, publishers, genres, categories, "
                "is_free, price_initial, price_final, price_discount_pct, price_currency, "
                "platform_windows, platform_mac, platform_linux, "
                "metacritic_score, metacritic_url, achievement_count, recommendation_count, "
                "dlc_appids, controller_support, required_age, "
                "buildid, build_timeupdated, depot_size_bytes, branch_names "
                "FROM app_details WHERE appid = ?",
                (details.appid,),
            ).fetchone()

            new_values: dict[str, str] = {
                "name":                 details.name,
                "app_type":             details.app_type,
                "short_description":    details.short_description,
                "supported_languages":  details.supported_languages,
                "website":              details.website,
                "header_image":         details.header_image,
                "background_image":     details.background_image,
                "early_access":         str(int(details.early_access)),
                "coming_soon":          str(int(details.coming_soon)),
                "release_date_str":     details.release_date_str,
                "developers":           json.dumps(details.developers),
                "publishers":           json.dumps(details.publishers),
                "genres":               json.dumps(details.genres),
                "categories":           json.dumps(details.categories),
                "is_free":              str(int(details.is_free)),
                "price_initial":        str(details.price_initial),
                "price_final":          str(details.price_final),
                "price_discount_pct":   str(details.price_discount_pct),
                "price_currency":       details.price_currency,
                "platform_windows":     str(int(details.platform_windows)),
                "platform_mac":         str(int(details.platform_mac)),
                "platform_linux":       str(int(details.platform_linux)),
                "metacritic_score":     str(details.metacritic_score),
                "metacritic_url":       details.metacritic_url,
                "achievement_count":    str(details.achievement_count),
                "recommendation_count": str(details.recommendation_count),
                "dlc_appids":           json.dumps(details.dlc_appids),
                "controller_support":   details.controller_support,
                "required_age":         str(details.required_age),
                "buildid":              str(details.buildid),
                "build_timeupdated":    str(details.build_timeupdated),
                "depot_size_bytes":     str(details.depot_size_bytes),
                "branch_names":         json.dumps(details.branch_names),
            }

            # Ordered list that matches the SELECT columns above
            field_names = [
                "name", "app_type", "short_description", "supported_languages",
                "website", "header_image", "background_image",
                "early_access", "coming_soon", "release_date_str",
                "developers", "publishers", "genres", "categories",
                "is_free", "price_initial", "price_final", "price_discount_pct",
                "price_currency",
                "platform_windows", "platform_mac", "platform_linux",
                "metacritic_score", "metacritic_url",
                "achievement_count", "recommendation_count",
                "dlc_appids", "controller_support", "required_age",
                "buildid", "build_timeupdated", "depot_size_bytes", "branch_names",
            ]

            changes: list[FieldChange] = []
            ts = datetime.now(tz=UTC)
            if old_row is not None:
                for i, field_name in enumerate(field_names):
                    old_val = str(old_row[i]) if old_row[i] is not None else None
                    new_val = new_values[field_name]
                    if old_val != new_val:
                        changes.append(FieldChange(
                            appid=details.appid,
                            field_name=field_name,
                            old_value=old_val,
                            new_value=new_val,
                            timestamp=ts,
                        ))

            if old_row is None:
                # First insert: persist baseline to field_history for future
                # diffs, but do NOT return them — avoids spurious alerts.
                for field_name, new_val in new_values.items():
                    baseline = FieldChange(
                        appid=details.appid,
                        field_name=field_name,
                        old_value=None,
                        new_value=new_val,
                        timestamp=ts,
                    )
                    con.execute(
                        "INSERT INTO field_history"
                        " (appid, field_name, old_value, new_value, timestamp)"
                        " VALUES (?, ?, ?, ?, ?)",
                        (
                            baseline.appid,
                            baseline.field_name,
                            baseline.old_value,
                            baseline.new_value,
                            baseline.timestamp.isoformat(),
                        ),
                    )

            # Persist the changes into field_history
            for change in changes:
                con.execute(
                    "INSERT INTO field_history"
                    " (appid, field_name, old_value, new_value, timestamp)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (
                        change.appid,
                        change.field_name,
                        change.old_value,
                        change.new_value,
                        change.timestamp.isoformat(),
                    ),
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
                     dlc_appids, controller_support, required_age,
                     buildid, build_timeupdated, depot_size_bytes, branch_names,
                     fetched_at)
                VALUES (?,?,?,?,?, ?,?,?, ?,?,?, ?,?,?,?, ?,?,?,?,?, ?,?,?, ?,?, ?,?,
                        ?,?,?, ?,?,?,?, ?)
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
                    dlc_appids           = excluded.dlc_appids,
                    controller_support   = excluded.controller_support,
                    required_age         = excluded.required_age,
                    buildid              = excluded.buildid,
                    build_timeupdated    = excluded.build_timeupdated,
                    depot_size_bytes     = excluded.depot_size_bytes,
                    branch_names         = excluded.branch_names,
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
                    json.dumps(details.dlc_appids),
                    details.controller_support,
                    details.required_age,
                    details.buildid,
                    details.build_timeupdated,
                    details.depot_size_bytes,
                    json.dumps(details.branch_names),
                    now,
                ),
            )

        return changes

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
                    "metacritic_score, metacritic_url, achievement_count, recommendation_count, "
                    "dlc_appids, controller_support, required_age, "
                    "buildid, build_timeupdated, depot_size_bytes, branch_names "
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
                        dlc_appids=json.loads(str(det[26])) if det[26] else [],
                        controller_support=str(det[27]) if det[27] is not None else "",
                        required_age=int(det[28]) if det[28] is not None else 0,
                        buildid=int(det[29]) if det[29] is not None else 0,
                        build_timeupdated=int(det[30]) if det[30] is not None else 0,
                        depot_size_bytes=int(det[31]) if det[31] is not None else 0,
                        branch_names=json.loads(str(det[32])) if det[32] else [],
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

    # ── Alerts ─────────────────────────────────────────────────────────────

    def upsert_alert(self, alert: Alert) -> None:
        """Insert an alert, silently ignoring duplicates (same deterministic ``id``).

        Args:
            alert: The :class:`~steam_tracker.models.Alert` to persist.
        """
        with self._connect() as con:
            con.execute(
                """
                INSERT OR IGNORE INTO alerts
                    (id, rule_name, rule_icon, appid, timestamp,
                     title, details, url, source_type, source_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alert.id,
                    alert.rule_name,
                    alert.rule_icon,
                    alert.appid,
                    alert.timestamp.isoformat(),
                    alert.title,
                    alert.details,
                    alert.url,
                    alert.source_type,
                    alert.source_id,
                ),
            )

    def get_alerts(
        self,
        *,
        rule_name: str | None = None,
        appid: int | None = None,
        since: datetime | None = None,
        limit: int = 1000,
    ) -> list[Alert]:
        """Return alerts, optionally filtered, ordered by timestamp descending.

        Args:
            rule_name: Restrict to a specific rule name.
            appid: Restrict to a specific app.
            since: Return only alerts newer than this timestamp.
            limit: Maximum number of results.

        Returns:
            List of :class:`~steam_tracker.models.Alert` objects.
        """
        query = (
            "SELECT a.id, a.rule_name, a.rule_icon, a.appid, g.name, "
            "a.timestamp, a.title, a.details, a.url, a.source_type, a.source_id "
            "FROM alerts a "
            "LEFT JOIN games g ON g.appid = a.appid "
            "WHERE 1=1"
        )
        params: list[object] = []
        if rule_name is not None:
            query += " AND a.rule_name = ?"
            params.append(rule_name)
        if appid is not None:
            query += " AND a.appid = ?"
            params.append(appid)
        if since is not None:
            query += " AND a.timestamp > ?"
            params.append(since.isoformat())
        query += f" ORDER BY a.timestamp DESC LIMIT {limit}"  # noqa: S608

        with self._connect() as con:
            rows = con.execute(query, params).fetchall()
        return [
            Alert(
                id=str(r[0]),
                rule_name=str(r[1]),
                rule_icon=str(r[2]),
                appid=int(r[3]),
                game_name=str(r[4]) if r[4] is not None else "",
                timestamp=datetime.fromisoformat(str(r[5])),
                title=str(r[6]),
                details=str(r[7]),
                url=str(r[8]),
                source_type=str(r[9]),
                source_id=str(r[10]),
            )
            for r in rows
        ]

    def get_alert_count_by_rule(self) -> dict[str, int]:
        """Return a mapping of ``rule_name → alert count``.

        Returns:
            Dict mapping each rule name to the number of stored alerts.
        """
        with self._connect() as con:
            rows = con.execute(
                "SELECT rule_name, COUNT(*) FROM alerts GROUP BY rule_name"
            ).fetchall()
        return {str(r[0]): int(r[1]) for r in rows}

    def get_field_history(
        self,
        *,
        appid: int | None = None,
        field_name: str | None = None,
        since: datetime | None = None,
    ) -> list[FieldChange]:
        """Return field history entries, optionally filtered.

        Args:
            appid: Restrict to a specific app.
            field_name: Restrict to a specific field.
            since: Return only changes newer than this timestamp.

        Returns:
            List of :class:`~steam_tracker.models.FieldChange` objects,
            ordered by timestamp descending.
        """
        query = (  # noqa: S608
            "SELECT appid, field_name, old_value, new_value, timestamp"
            " FROM field_history WHERE 1=1"
        )
        params: list[object] = []
        if appid is not None:
            query += " AND appid = ?"
            params.append(appid)
        if field_name is not None:
            query += " AND field_name = ?"
            params.append(field_name)
        if since is not None:
            query += " AND timestamp > ?"
            params.append(since.isoformat())
        query += " ORDER BY timestamp DESC"

        with self._connect() as con:
            rows = con.execute(query, params).fetchall()
        return [
            FieldChange(
                appid=int(r[0]),
                field_name=str(r[1]),
                old_value=str(r[2]) if r[2] is not None else None,
                new_value=str(r[3]),
                timestamp=datetime.fromisoformat(str(r[4])),
            )
            for r in rows
        ]

    # ── Diagnostic methods ─────────────────────────────────────────────────

    def get_all_appid_mappings(self) -> list[dict[str, object]]:
        """Return all rows from the ``appid_mappings`` table.

        Each dict contains: ``external_source``, ``external_id``,
        ``external_name``, ``steam_appid`` (int|None), ``resolved_at``,
        ``manual`` (bool).

        Returns:
            List of mapping dicts ordered by external_name.
        """
        with self._connect() as con:
            rows = con.execute(
                "SELECT external_source, external_id, external_name, "
                "steam_appid, resolved_at, manual "
                "FROM appid_mappings ORDER BY external_name COLLATE NOCASE"
            ).fetchall()
        return [
            {
                "external_source": str(r[0]),
                "external_id": str(r[1]),
                "external_name": str(r[2]),
                "steam_appid": int(r[3]) if r[3] is not None else None,
                "resolved_at": str(r[4]),
                "manual": bool(r[5]),
            }
            for r in rows
        ]

    def get_diagnostic_summary(self) -> dict[str, object]:
        """Return aggregate counts useful for the diagnostic page.

        Returns:
            Dict with keys: ``total_games``, ``by_source`` (dict),
            ``enriched_count``, ``unenriched_count``, ``total_mappings``,
            ``resolved_mappings``, ``unresolved_mappings``,
            ``manual_mappings``, ``total_alerts``, ``total_news``.
        """
        with self._connect() as con:
            total_games = con.execute("SELECT COUNT(*) FROM games").fetchone()[0]
            by_source_rows = con.execute(
                "SELECT source, COUNT(*) FROM games GROUP BY source"
            ).fetchall()
            by_source = {str(r[0]): int(r[1]) for r in by_source_rows}

            enriched = con.execute(
                "SELECT COUNT(*) FROM app_details"
            ).fetchone()[0]
            total_mappings = con.execute(
                "SELECT COUNT(*) FROM appid_mappings"
            ).fetchone()[0]
            resolved_mappings = con.execute(
                "SELECT COUNT(*) FROM appid_mappings WHERE steam_appid IS NOT NULL"
            ).fetchone()[0]
            manual_mappings = con.execute(
                "SELECT COUNT(*) FROM appid_mappings WHERE manual = 1"
            ).fetchone()[0]
            total_alerts = con.execute(
                "SELECT COUNT(*) FROM alerts"
            ).fetchone()[0]
            total_news = con.execute(
                "SELECT COUNT(*) FROM news"
            ).fetchone()[0]

        return {
            "total_games": int(total_games),
            "by_source": by_source,
            "enriched_count": int(enriched),
            "unenriched_count": int(total_games) - int(enriched),
            "total_mappings": int(total_mappings),
            "resolved_mappings": int(resolved_mappings),
            "unresolved_mappings": int(total_mappings) - int(resolved_mappings),
            "manual_mappings": int(manual_mappings),
            "total_alerts": int(total_alerts),
            "total_news": int(total_news),
        }
