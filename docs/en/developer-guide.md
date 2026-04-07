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
8. [CI/CD](#8-cicd)
9. [Adding a translation](#9-adding-a-translation)
10. [Adding a game source](#10-adding-a-game-source)
11. [Contributing](#11-contributing)

---

## 1. Project layout

```
steam_tracker/
├── __init__.py
├── models.py      # Pydantic v2 domain models
├── api.py         # Typed Steam API wrappers (enrichment only: details + news)
├── epic_api.py    # Epic Games OAuth2 + library API wrappers
├── gog_api.py     # GOG Galaxy OAuth2 + library API wrappers
├── gamepass_api.py# Xbox Game Pass public catalog API
├── resolver.py    # Steam AppID resolver chain (IGDB, Steam Store Search)
├── db.py          # SQLite persistence layer
├── fetcher.py     # Multi-threaded fetcher + rate limiter
├── renderer.py    # Static HTML generator + sidecar config page
├── server.py      # Sidecar HTTP server (steam-serve)
├── cli.py         # steam-fetch / steam-render / steampulse entry points
├── sources/
│   ├── __init__.py    # GameSource Protocol + get_all_sources() registry
│   ├── steam.py       # SteamSource: owned library, wishlist, followed games
│   ├── epic.py        # EpicSource: Epic Games Store library
│   ├── gog.py         # GogSource: GOG Galaxy library
│   └── gamepass.py    # GamePassSource: Xbox PC Game Pass catalog
└── i18n/
    ├── __init__.py  # Translator, get_translator(), detect_lang()
    ├── en.py        # English strings
    └── fr.py        # French strings
tests/
├── conftest.py
├── test_api.py
├── test_db.py
├── test_epic.py
├── test_fetcher.py
├── test_gog_api.py
├── test_gamepass_api.py
├── test_renderer.py
├── test_resolver.py
├── test_server.py
└── test_sources.py
docs/
├── en/            # English documentation
└── fr/            # French documentation
pyproject.toml
README.md
CHANGELOG.md
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
| `source` | `str` | `"owned"` \| `"wishlist"` \| `"followed"` \| `"epic"` |
| `external_id` | `str` | External identifier (e.g. `"epic:<catalogItemId>"`) — empty for native Steam games |

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

Three main tables plus an AppID mapping cache; foreign keys enforced; WAL journal mode.

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
    source            TEXT    NOT NULL DEFAULT 'owned',
    external_id       TEXT    NOT NULL DEFAULT ''
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

-- Map external store game IDs to Steam AppIDs
CREATE TABLE appid_mappings (
    external_source TEXT NOT NULL,   -- "epic", "gog", ...
    external_id     TEXT NOT NULL,   -- store-specific catalog ID
    external_name   TEXT NOT NULL,   -- game name on the external store
    steam_appid     INTEGER,         -- NULL if unresolved
    resolved_at     TEXT NOT NULL,
    manual          INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (external_source, external_id)
);
```

### Additive migrations

New columns are added via `_MIGRATIONS` in `db.py` — a list of `(table, column, column_definition)` tuples applied as `ALTER TABLE … ADD COLUMN` if the column does not yet exist. This keeps existing databases compatible without a migration framework.

### Source priority in upserts

When the same game appears in multiple sources, `upsert_game` uses a SQL `CASE WHEN` expression to enforce the priority: **owned > epic > gog > gamepass > wishlist > followed**. Playtime and timestamps are only updated for `source = 'owned'` games.

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
| `get_appid_mapping(source, external_id)` | Cached Steam AppID for an external game, or `None` |
| `upsert_appid_mapping(source, external_id, name, steam_appid, manual)` | Insert/update an AppID mapping; manual mappings protected from auto-overwrite |
| `run_cleanup()` | Run all registered data-cleanup rules; returns total rows affected |

#### Data cleanup system

`Database.run_cleanup()` executes a list of cleanup rules stored in the class attribute `_CLEANUP_RULES`. Each rule is a method `_cleanup_*(self) -> int` that fixes or removes stale/broken data from previous runs. The method returns the total number of affected rows across all rules.

Cleanup runs **automatically** at the beginning of every `cmd_fetch` / `cmd_run` invocation, before game discovery. If any rows were cleaned, a message is printed to the user.

**Adding a new cleanup rule:**

1. Add a private method `_cleanup_<description>(self) -> int` to the `Database` class
2. The method should fix or remove bad data and return the number of affected rows
3. Append the method reference to `_CLEANUP_RULES`

**Current rules:**

| Rule | Purpose |
|---|---|
| `_cleanup_epic_live_name` | Removes Epic games named `"Live"` (caused by a bug that used the `sandboxName` field — the deployment environment label — instead of the real game title). Also deletes the corresponding `appid_mappings` entries so that the resolver retries clean discovery on the next fetch. |
| `_cleanup_epic_hex_id_name` | Removes Epic games whose name is a long hex catalog ID (24+ lowercase hex chars, e.g. `91eac4ac00304bcc…`). |
| `_cleanup_epic_production_name` | Removes Epic games with internal sandbox names matching `^\w+ Production$` (e.g. "coffee Production", "boysenberry Production") and their `appid_mappings` entries. |
| `_cleanup_epic_duplicate_external_id` | Removes duplicate Epic entries where both a real-appid (< 2 billion) and a synthetic-appid (≥ 2 billion) row exist for the same `external_id`; keeps the real-appid entry and deletes the synthetic one along with its `appid_mappings`. |

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

Public functions: `write_html` (library page), `write_alerts_html` (alerts page), and `render_config_page` (sidecar config page). `write_html` and `write_alerts_html` accept a `steam_id` string for the header, an output `Path`, an optional cross-link href, and an optional `lang` code. `write_html` takes a `list[GameRecord]`, while `write_alerts_html` takes a `list[Alert]` and a `dict[int, GameRecord]`.

`render_config_page(config, lang, is_bootstrap)` returns a self-contained HTML string with a form for all configurable fields. Credential fields are shown as masked password inputs. The function is used by the sidecar server at `GET /config`.

The HTML is built by string interpolation into `_HTML_TEMPLATE` and `_ALERTS_TEMPLATE` raw strings. No external templating library is used. Visible labels use `__T_key__` placeholders replaced at render time via `_apply_html_t()`; JavaScript strings are injected as a `const I18N = {...}` block via `_build_i18n_js()`.

`_build_sidecar_js()` builds the feature-detection block that probes `/api/ping`, handles action buttons, and polls `/api/status` every 3 seconds to display a fetch-progress bandeau.

### `sources/__init__.py — GameSource`

| Symbol | Description |
|---|---|
| `GameSource` | `runtime_checkable` Protocol — any class with `name`, `add_arguments()`, `is_enabled()`, `discover_games()` satisfies it |
| `get_all_sources()` | Returns a new list of all registered `GameSource` instances: `SteamSource`, `EpicSource`, `GogSource`, `GamePassSource` |

### `sources/steam.py — SteamSource`

`SteamSource` implements `GameSource` for Steam.  It registers `--key`, `--steamid`, `--no-wishlist`, and `--followed` as CLI arguments and delegates to the three `api.py` discovery functions.

`discover_games(args)` returns **all** games across sub-sources (owned, then wishlist, then followed) — possibly with the same `appid` under different `source` labels.  The CLI upserts all of them to the database (which enforces `owned > wishlist > followed` priority) and builds a deduplicated list for the fetcher.

### `sources/epic.py — EpicSource`

`EpicSource` implements `GameSource` for the Epic Games Store.  It registers `--epic-auth-code`, `--epic-refresh-token`, `--epic-account-id`, `--twitch-client-id`, and `--twitch-client-secret` as CLI arguments.

`is_enabled(args)` returns `True` if an auth code, or a refresh token together with an account ID, is provided.

`discover_games(args)` authenticates with Epic, fetches the library, queries the Catalog API for **all** items to get authoritative titles (using `_extract_epic_title()` only as fallback), and for each game:
- Resolves the Steam AppID via `resolve_steam_appid()` (Steam Store Search fallback)
- If resolved: sets `appid = steam_appid` for full enrichment
- If unresolved: generates a deterministic hash-based appid (≥ 2,000,000,000)
- All games get `source="epic"` and `external_id="epic:<catalogItemId>"`

### `sources/gog.py — GogSource`

`GogSource` implements `GameSource` for GOG Galaxy. It registers `--gog-refresh-token` as a CLI argument.

`is_enabled(args)` returns `True` if `args.gog_refresh_token` is set.

`discover_games(args)` calls `gog_auth_with_refresh()`, saves the renewed token back to the config, fetches the full GOG library via `gog_get_all_products()`, and resolves each game to a Steam AppID. Unresolved games get a synthetic hash-based appid. All games get `source="gog"` and `external_id="gog:<productId>"`.

### `sources/gamepass.py — GamePassSource`

`GamePassSource` implements `GameSource` for Xbox PC Game Pass. It registers `--game-pass` (store_true) as a CLI argument. No authentication is required — the catalog is public.

`is_enabled(args)` returns `True` if `args.gamepass` is truthy.

`discover_games(args)` calls `gamepass_get_catalog_ids()` then `gamepass_get_titles()` and resolves each title to a Steam AppID. Unresolved games get a synthetic hash-based appid. All games get `source="gamepass"` and `external_id="gamepass:<storeId>"`.

### `gog_api.py`

| Function | Description |
|---|---|
| `gog_auth_with_code(auth_code)` | Exchange a GOG authorization code for a token (OAuth2, GET request) |
| `gog_auth_with_refresh(refresh_token)` | Renew the session using a saved refresh token |
| `gog_get_all_products(access_token, session=None)` | Fetch the full GOG library (paginated `embed.gog.com` API) |

### `gamepass_api.py`

| Function | Description |
|---|---|
| `gamepass_get_catalog_ids(session=None)` | Fetch the list of Game Pass store IDs from the Microsoft `catalog.gamepass.com/sigls/v2` endpoint |
| `gamepass_get_titles(store_ids, session=None)` | Batch-resolve store IDs to human-readable titles via `displaycatalog.mp.microsoft.com` (batches of 20) |

### `resolver.py`

| Symbol | Description |
|---|---|
| `AppIdResolver` | Protocol — any class with `resolve(name, session) → int \| None` satisfies it |
| `SteamStoreResolver` | Resolves via Steam Store Search API with multi-strategy matching: (1) fuzzy similarity (SequenceMatcher ≥ 0.8), (2) word-prefix with sequel rejection, (3) normalized word-containment; retries with edition-suffix stripping and year normalization |
| `IGDBResolver(twitch_client_id, twitch_client_secret)` | Resolves via IGDB: Twitch OAuth → game search → external_games lookup (category=Steam) |
| `resolve_steam_appid(name, resolvers, session)` | Iterates resolvers in order; first successful result wins |

### `epic_api.py`

| Function | Description |
|---|---|
| `epic_auth_with_code(auth_code)` | Exchange an Epic authorization code for an access + refresh token |
| `epic_auth_with_refresh(refresh_token)` | Renew the session using a saved refresh token (valid 30 days, auto-renewed on each use) |
| `epic_auth_with_device(device_id, account_id, secret)` | Authenticate using persistent device credentials (kept for advanced use) |
| `epic_get_library(access_token)` | Fetch the user's Epic library with pagination |
| `epic_get_catalog_titles(items, session=None)` | Batch-resolve catalog item IDs to human-readable titles via Epic's public catalog endpoint (batches of 50); groups items by namespace internally |

### `i18n/__init__.py`

| Symbol | Description |
|---|---|
| `detect_lang()` | Reads env vars `LANGUAGE` / `LC_ALL` / `LC_MESSAGES` / `LANG` then `locale.getdefaultlocale()`, returns a 2-letter code, default `"en"` |
| `Translator` | Callable class; `t("key")` returns the translated string, `t("key", param=val)` performs `str.format` substitution; falls back to English for missing keys |
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

## 8. CI/CD

Two GitHub Actions workflows live in `.github/workflows/`.

### `ci.yml` — Quality gate

Triggers on every **push** or **pull request** targeting `main` or `master`.

| Property | Value |
|---|---|
| Runner | `windows-latest` |
| Python matrix | 3.11 · 3.12 · 3.13 |
| Install command | `pip install -e ".[dev]"` |

**Steps (in order):**

1. `ruff check steam_tracker` — linting, zero warnings required
2. `mypy steam_tracker` — strict type checking, zero errors required
3. `pytest -q --tb=short` — full test suite

All three steps must pass on all three Python versions for the workflow to succeed. The workflow does **not** publish any artifact.

### `build.yml` — Windows EXE release

Triggers on:
- a **tag push** matching `v*.*.*` (e.g. `v1.2.0`) → full build + GitHub Release
- a **manual dispatch** (`workflow_dispatch`) → build + artifact upload only (no release)

| Property | Value |
|---|---|
| Runner | `windows-latest` |
| Python | 3.11 (fixed) |
| Install command | `pip install -e ".[build]"` |
| Permissions | `contents: write` (needed to publish a GitHub Release) |

**Steps (in order):**

1. **Build** — runs `pyinstaller steampulse.spec` from the `build/` directory; produces `dist/steampulse.exe`.
2. **Smoke test** — runs `dist\steampulse.exe --help` to verify the executable starts correctly.
3. **Version** — reads the package version via `importlib.metadata` and exposes it as `VERSION` output.
4. **Archive** — compresses `steampulse.exe` into `steampulse-v<VERSION>-windows-x64.zip`.
5. **Upload artifact** — always uploads the zip as a workflow artifact (available for download from the Actions run page).
6. **Release notes** — extracts the section for the current version from `CHANGELOG.md` using a PowerShell regex; falls back to a link to the changelog if the section is not found.
7. **Publish release** *(tag pushes only)* — creates or updates the GitHub Release for the tag using `softprops/action-gh-release@v2`, attaching the zip and the extracted release notes.

### Triggering a release

```bash
# Tag the commit and push — build.yml fires automatically
git tag v1.2.0
git push origin v1.2.0
```

Update `CHANGELOG.md` with a `## [1.2.0]` section **before** pushing the tag so the release notes are extracted correctly.

---

## 9. Adding a translation

1. Create `steam_tracker/i18n/<code>.py` (e.g. `de.py` for German) with a single `STRINGS: dict[str, str]` that mirrors the keys in `en.py`. You only need to provide the keys you want to translate — missing keys fall back to English automatically.

2. Register the module in `steam_tracker/i18n/__init__.py`:
   ```python
   _SUPPORTED = {"en": en, "fr": fr, "de": de}   # add your import and entry
   ```

3. Users can then pass `--lang de` or set a German system locale.

---

## 10. Adding a game source

To add a new game source plugin (e.g. GOG, Epic Games):

1. **Create `steam_tracker/sources/<name>.py`** with a class that satisfies the `GameSource` protocol:

   ```python
   class GogSource:
       name = "gog"

       def add_arguments(self, parser: argparse.ArgumentParser) -> None:
           parser.add_argument("--gog-token", help="GOG OAuth token")

       def is_enabled(self, args: argparse.Namespace) -> bool:
           return bool(getattr(args, "gog_token", None))

       def discover_games(self, args: argparse.Namespace) -> list[OwnedGame]:
           # fetch from GOG API, map to OwnedGame with source="gog"
           ...
   ```

2. **Register the source** in `steam_tracker/sources/__init__.py`:

   ```python
   def get_all_sources() -> list[GameSource]:
       from .steam import SteamSource
       from .gog import GogSource  # add this
       return [SteamSource(), GogSource()]  # add instance
   ```

3. **Map to Steam AppIDs** — The enrichment pipeline (details, news) works via Steam AppIDs.  Use the resolver system in `steam_tracker/resolver.py` (`SteamStoreResolver` for zero-config fuzzy matching, `IGDBResolver` if Twitch/IGDB credentials are available) via `resolve_steam_appid(name, resolvers)`.  Resolved AppIDs can be cached in the `appid_mappings` table.  If no AppID is found, set a deterministic hash-based appid (≥ 2,000,000,000) and a non-empty `external_id` — the CLI will exclude these games from the Steam enrichment pipeline.

4. **Add tests** in `tests/test_sources.py` — cover `add_arguments`, `is_enabled`, and `discover_games` with mocked HTTP calls.

---

## 11. Contributing

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
