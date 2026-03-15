# SteamPulse — Developer Guide

🌐 [Version française](../fr/developer-guide.md)

## Table of contents

1. [Project layout](#1-project-layout)
2. [Architecture overview](#2-architecture-overview)
3. [Data models](#3-data-models)
4. [Database schema](#4-database-schema)
5. [Module reference](#5-module-reference)
6. [Running tests](#6-running-tests)
7. [Linting & type checking](#7-linting--type-checking)
8. [Adding a translation](#8-adding-a-translation)
9. [Adding a data source](#9-adding-a-data-source)
10. [Contributing](#10-contributing)

---

## 1. Project layout

```
steampulse/
├── steam_tracker/
│   ├── __init__.py
│   ├── models.py      # Pydantic v2 domain models
│   ├── api.py         # Typed Steam API wrappers
│   ├── db.py          # SQLite persistence layer
│   ├── fetcher.py     # Multi-threaded fetcher + rate limiter
│   ├── renderer.py    # Static HTML generator
│   ├── cli.py         # steam-fetch / steam-render entry points
│   └── i18n/
│       ├── __init__.py  # Translator, get_translator(), detect_lang()
│       ├── en.py        # English strings
│       └── fr.py        # French strings
├── tests/
│   ├── conftest.py
│   ├── test_api.py
│   ├── test_db.py
│   ├── test_fetcher.py
│   └── test_renderer.py
├── docs/
│   ├── en/            # English documentation
│   └── fr/            # French documentation
├── pyproject.toml
├── README.md
└── CHANGELOG.md
```

---

## 2. Architecture overview

```
Steam Web API ──┐
Steam Store API ─┤  api.py  ──►  fetcher.py  ──►  db.py  ──►  renderer.py  ──►  HTML
                │  (HTTP wrappers)  (ThreadPool)  (SQLite)   (Jinja-free)
Wishlist API ───┘
```

**Data flow:**

1. `cli.py:cmd_fetch` calls `api.py` to retrieve owned games / wishlist / followed games
2. Each `OwnedGame` is upserted into the `games` table immediately
3. `fetcher.py:SteamFetcher.fetch_all()` dispatches concurrent requests for app details and news
   - Games with fresh cached details are skipped (`skip_appids`)
   - Games with stale news (> `--news-age` hours) get news-only re-fetches (`refresh_news_appids`)
4. Results are persisted via `db.py:upsert_app_details` and `db.py:upsert_news`
5. `cli.py:cmd_render` reads all records from `db.py:get_all_game_records` and passes them to `renderer.py`

---

## 3. Data models

All models live in `steam_tracker/models.py` and use **Pydantic v2**.

### `OwnedGame`

Represents a game entry from any source.

| Field | Type | Description |
|---|---|---|
| `appid` | `int` | Steam App ID |
| `name` | `str` | Display name |
| `playtime_forever` | `int` | Total minutes played |
| `playtime_2weeks` | `int` | Minutes played last 2 weeks |
| `rtime_last_played` | `int` | Unix timestamp of last session |
| `img_icon_url` | `str` | Icon URL fragment |
| `img_logo_url` | `str` | Logo URL fragment |
| `source` | `str` | `"owned"` \| `"wishlist"` \| `"followed"` |

### `AppDetails`

Rich metadata from the Steam Store API.

| Field | Type | Description |
|---|---|---|
| `appid` | `int` | Steam App ID |
| `name` | `str` | Store name |
| `app_type` | `str` | `"game"`, `"dlc"`, `"demo"`, … |
| `short_description` | `str` | Store short description |
| `early_access` | `bool` | Is in Early Access |
| `coming_soon` | `bool` | Not yet released |
| `release_date_str` | `str` | Human-readable release date |
| `developers` / `publishers` | `list[str]` | Studio names |
| `genres` / `categories` | `list[str]` | Taxonomy tags |
| `is_free` | `bool` | Free-to-play |
| `price_initial` / `price_final` | `int` | Cents in store currency |
| `price_discount_pct` | `int` | Discount percentage |
| `price_currency` | `str` | ISO currency code |
| `platform_windows/mac/linux` | `bool` | Platform availability |
| `metacritic_score` | `int` | 0–100 |
| `metacritic_url` | `str` | Metacritic page URL |
| `achievement_count` | `int` | Number of achievements |
| `recommendation_count` | `int` | Number of Steam reviews |
| `header_image` / `background_image` | `str` | CDN image URLs |
| `supported_languages` | `str` | Raw HTML string from Steam |
| `website` | `str` | Official website URL |
| `fetched_at` | `datetime` | UTC timestamp of last fetch |

### `NewsItem`

A single news article.

| Field | Type | Description |
|---|---|---|
| `appid` | `int` | Parent game App ID |
| `gid` | `str` | Steam news GID |
| `title` | `str` | Article title |
| `date` | `datetime` | Publication date (UTC) |
| `url` | `str` | Full article URL |
| `author` | `str` | Author name |
| `feedname` / `feedlabel` | `str` | Feed identifier / display name |
| `tags` | `list[str]` | Tag list |
| `fetched_at` | `datetime` | UTC timestamp of last fetch |

### `GameRecord`

Denormalised aggregate passed to the renderer.

```python
@dataclass
class GameRecord:
    game: OwnedGame
    details: AppDetails | None
    news: list[NewsItem]
    status: GameStatus
```

### `GameStatus`

```python
@dataclass
class GameStatus:
    label: str    # Human-readable ("Sorti (1.0)", "Early Access", …)
    badge: str    # CSS class ("released", "earlyaccess", "unreleased", "unknown")
    release_date: str
```

---

## 4. Database schema

Three tables; foreign keys enforced; WAL journal mode.

```sql
-- One row per Steam appid tracked
CREATE TABLE games (
    appid             INTEGER PRIMARY KEY,
    name              TEXT    NOT NULL,
    playtime_forever  INTEGER NOT NULL DEFAULT 0,
    playtime_2weeks   INTEGER NOT NULL DEFAULT 0,
    rtime_last_played INTEGER NOT NULL DEFAULT 0,
    img_icon_url      TEXT    NOT NULL DEFAULT '',
    img_logo_url      TEXT    NOT NULL DEFAULT '',
    last_seen_at      TEXT    NOT NULL,
    source            TEXT    NOT NULL DEFAULT 'owned'
);

-- One row per appid (app metadata from the Store API)
CREATE TABLE app_details (
    appid                INTEGER PRIMARY KEY REFERENCES games(appid) ON DELETE CASCADE,
    name                 TEXT    NOT NULL DEFAULT '',
    -- ... (all AppDetails fields)
    fetched_at           TEXT    NOT NULL
);

-- Multiple rows per appid (news items)
CREATE TABLE news (
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
```

### Additive migrations

New columns are added via `_MIGRATIONS` in `db.py` — a list of `(table, column, column_definition)` tuples applied as `ALTER TABLE … ADD COLUMN` if the column does not yet exist. This keeps existing databases compatible without a migration framework.

### Source priority in upserts

When the same game appears in multiple sources, `upsert_game` uses a SQL `CASE WHEN` expression to enforce the priority: **owned > wishlist > followed**. Playtime and timestamps are only updated for `source = 'owned'` games.

---

## 5. Module reference

### `api.py`

| Function | Endpoint | Description |
|---|---|---|
| `get_owned_games(key, steamid)` | `IPlayerService/GetOwnedGames/v1` | Returns `list[OwnedGame]` |
| `get_wishlist(key, steamid)` | `IWishlistService/GetWishlist/v1` | Returns `list[OwnedGame]` with `source="wishlist"` |
| `get_followed_games(key, steamid)` | `IPlayerService/GetFollowedGames/v1` | Returns `list[OwnedGame]` with `source="followed"` (usually empty) |
| `get_app_details(appid)` | `store.steampowered.com/api/appdetails` | Returns `AppDetails \| None` |
| `get_app_news(appid, count)` | `ISteamNews/GetNewsForApp/v2` | Returns `list[NewsItem]` |

HTTP 403/404 on news/details endpoints → logged at DEBUG (not a warning — Steam regularly returns these for DLCs and non-game apps).

### `db.py — Database`

| Method | Description |
|---|---|
| `upsert_game(game)` | Insert or update a game row (source priority enforced) |
| `upsert_app_details(details)` | Insert or replace app_details; backfills empty game name |
| `upsert_news(appid, items)` | Insert news items (INSERT OR IGNORE on duplicate URL) |
| `get_cached_appids()` | Set of appids already in app_details |
| `get_stale_news_appids(max_age_s)` | Set of appids with no news or news older than `max_age_s` seconds |
| `get_all_game_records()` | Full denormalised list for the renderer |

### `fetcher.py — SteamFetcher`

```python
SteamFetcher(
    rate_limit: float = 1.5,   # seconds between app_details requests (shared across threads)
    max_workers: int = 4,
    news_per_game: int = 5,
    on_progress: Callable[[int, int, str], None] | None = None,
)
```

`fetch_all(games, skip_appids, refresh_news_appids)` returns `dict[int, tuple[AppDetails | None, list[NewsItem]]]`.

- `skip_appids` — games to skip entirely
- `refresh_news_appids` — subset of skipped games that should get their news re-fetched (no rate limiting — news endpoint is not restricted)

### `renderer.py`

Two public functions: `write_html` and `write_news_html`. Both accept a `list[GameRecord]`, a `steam_id` string for the header, an output `Path`, an optional cross-link href, and an optional `lang` code.

The HTML is built by string interpolation into `_HTML_TEMPLATE` and `_NEWS_TEMPLATE` raw strings. No external templating library is used. Visible labels use `__T_key__` placeholders replaced at render time via `_apply_html_t()`; JavaScript strings are injected as a `const I18N = {...}` block via `_build_i18n_js()`.

### `i18n/__init__.py`

| Symbol | Description |
|---|---|
| `detect_lang()` | Reads `LANGUAGE` / `LC_ALL` / `LC_MESSAGES` / `LANG` env vars then `locale.getdefaultlocale()`, returns a 2-letter code, defaults to `"en"` |
| `Translator` | Callable class; `t("key")` returns the translated string, `t("key", param=val)` performs `str.format` substitution; falls back to English if the key is missing |
| `get_translator(lang)` | Returns a `Translator` for the given lang code (or auto-detected); unknown codes fall back to `"en"` |

---

## 6. Running tests

```bash
# Run all tests with coverage
pytest

# Quick (no coverage)
pytest -q --no-cov

# Single module
pytest tests/test_api.py -v
```

Tests use `responses` to mock HTTP calls and `pytest` fixtures defined in `conftest.py`.

Coverage report is printed to the terminal; an HTML report can be generated with:

```bash
pytest --cov-report=html
# then open htmlcov/index.html
```

---

## 7. Linting & type checking

```bash
# Linting (ruff)
ruff check steam_tracker

# Auto-fix
ruff check steam_tracker --fix

# Type checking (mypy strict)
mypy steam_tracker
```

Configuration lives in `pyproject.toml` under `[tool.ruff]` and `[tool.mypy]`.

Notable settings:
- Line length: **100** (E501 ignored in `renderer.py` due to long inline CSS/JS)
- mypy: `strict = true`
- ruff selects: `E F W I UP N B A C4 SIM`

---

## 8. Adding a translation

1. Create `steam_tracker/i18n/<code>.py` (e.g. `de.py` for German) with a single `STRINGS: dict[str, str]` that mirrors the keys in `en.py`. You only need to provide the keys you want to translate — missing keys fall back to English automatically.

2. Register the module in `steam_tracker/i18n/__init__.py`:
   ```python
   _SUPPORTED = {"en": en, "fr": fr, "de": de}   # add your import and entry
   ```

3. Users can then pass `--lang de` or set a German system locale.

---

## 9. Adding a data source

To add a new game source (e.g. Epic Games, GOG):

1. **`models.py`** — add the new value to the `source` field docstring/comment (the field is a plain `str`, no enum).

2. **`api.py`** — write a new `get_<source>_games(...)` function returning `list[OwnedGame]` with `source="<source>"`.

3. **`db.py`** — update the `CASE WHEN` source-priority expression in `upsert_game` if the new source needs a specific priority.

4. **`cli.py`** — add a `--<source>` / `--no-<source>` flag in `cmd_fetch`, call your new API function, upsert results, and append new games to the `games` list.

5. **`renderer.py`** — optionally add a filter button in `_HTML_TEMPLATE` (the `#sourceBtns` div) and a display label in `make_card()`.

6. **Tests** — add unit tests in `tests/test_api.py` and integration tests in `tests/test_db.py`.

---

## 10. Contributing

```bash
# 1. Create a branch
git checkout -b feat/my-feature

# 2. Make changes, add tests
# 3. Verify everything passes
ruff check steam_tracker
mypy steam_tracker
pytest

# 4. Commit (conventional commits recommended)
git commit -m "feat: add Epic Games source"

# 5. Open a pull request against main
```

**Commit style:** `feat:` · `fix:` · `refactor:` · `docs:` · `test:` · `chore:`

**Before opening a PR:**
- All ruff checks pass (no `--fix` shortcuts committed)
- mypy reports zero errors
- All existing tests pass; new behaviour is covered by tests
- `CHANGELOG.md` is updated under `[Unreleased]`
