# Changelog

All notable changes to SteamPulse will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).  
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added

- **GOG Galaxy source** — new `--gog-refresh-token` flag (or `[gog] refresh_token` in config TOML) fetches your GOG library via the GOG OAuth2 + embed API; games are tagged `gog` and enriched with Steam AppID via the existing resolver chain; the setup wizard (step 3/6) guides the user through the one-time browser auth flow
- **Xbox PC Game Pass source** — new `--game-pass` flag (or `gamepass = true` in config) fetches all current PC Game Pass titles from the public Microsoft catalog; no authentication required; games are tagged `gamepass`
- **Web configuration page (`/config`)** — served by the `steam-serve` sidecar at `/config`; lets users view and edit all credentials and settings in a browser form without touching the TOML file directly; accessible without authentication in bootstrap mode (no `serve_token` configured); credential fields are never pre-filled (shown as `● ● ●` placeholder if already set)
- **`POST /api/config`** — JSON endpoint that saves the submitted config fields to the TOML file; ignores empty-string and `***` values so masked credential placeholders can never accidentally overwrite real secrets
- **`GET /api/config`** — returns the current config as JSON with all credential fields masked as `***`
- **Auto-restart on token change** — when `serve_token` is changed via the web UI, the sidecar calls `os._exit(0)` after a 0.5 s delay (relying on supervisord autorestart) and the browser polls `/api/ping` until the server comes back up, then redirects to `/login`
- **Fetch-progress bandeau** — the library page now shows a fixed top banner while a background fetch is running (polling `/api/status` every 3 s); the banner displays current progress (`idx/total` + game name) and automatically reloads the page when the fetch completes
- **`GET /api/status`** — public endpoint returning live fetch state (`fetching`, `current`, `idx`, `total`); used by the progress bandeau
- **GOG & Game Pass store filter buttons** — library and alerts filter panels now include dedicated `🌌 GOG` and `🎯 Game Pass` store buttons alongside the existing Steam and Epic buttons
- **Store filter multiselect toggle** — a small "multi" checkbox next to the Store filter label switches between exclusive mode (click = select only that store, default) and multi-select mode (click = toggle individual store); state persisted in `localStorage` and URL hash
- **Config icon in auth dock** — ⚙ icon link to `/config` added to the sidecar auth panel in the library page header; visible whenever `steam-serve` is running, regardless of authentication state

### Fixed

- **`SYNTHETIC_APPID_BASE` unused in `sources/epic.py`** — removed stale import; `hash_synthetic_appid` is sufficient

---

## [2.0.0] — 2026-04-04

### Added

- **`steam-serve` sidecar server** — new `steam-serve` command starts a lightweight HTTP server (stdlib only, zero new dependencies) that serves the HTML dashboards and exposes a small mutation API (`/api/ping`, `/api/mark-removed/{appid}`, `/api/mark-active/{appid}`, `/api/delete/{appid}`); HTML pages re-render instantly after each mutation
- **Interactive action buttons on library cards** — when `steam-serve` is running the library page shows ⛔ / ↩️ / 🗑️ action buttons on each game card for quick soft-delete, reactivation, and hard-delete; buttons are hidden in read-only mode (native file-open)
- **Graceful degradation** — HTML pages remain fully functional read-only dashboards when `steam-serve` is not running; the JS feature-detection probe (`/api/ping`) is fire-and-forget with a 2-second timeout
- **Soft-delete for removed games** — when a game disappears from all sources during a fetch, it is automatically tagged `removed_at` (ISO timestamp) rather than deleted; reappearing games are automatically reactivated
- **Availability filter** — new filter group in the library page lets users show "Active" games only (default), all games, or "Removed" games only; filter state is saved in the URL hash and local storage
- **`--mark-removed <APPID>`** — CLI flag to manually mark a game as removed (soft-delete) without running a full fetch
- **`--delete <APPID>`** — CLI flag to permanently delete a game and all its associated data from the database
- **Removed badge on cards** — games tagged as removed display a grey "Removed" badge with the removal date as tooltip; card is dimmed (opacity + grayscale)
- **Date-added tracking** — database column `time_added` (Unix timestamp) records when a game is first inserted; preserved on subsequent upserts
- **Sort by date added** — new "Date d'ajout ↓" / "Sort: Date added ↓" option in the library sort dropdown; games with no tracked date sort to the bottom
- **Date-added display on cards** — cards show ➕ date when a `time_added` value is available (new games only; existing games show nothing until they are re-encountered on a new fetch)
- **Short date format on cards** — all dates on game cards (release date, last news, date added, in-card news list) now use `dd/mm/yy` instead of a long locale string; news dates on the alerts page are unchanged
- **Cookie-based authentication for `steam-serve`** — new `--token` flag enables auth mode; login form at `/login` issues an `HttpOnly`/`SameSite=Strict` session cookie; token comparison uses `hmac.compare_digest()` to prevent timing attacks; `steam_diagnostic.html` is protected behind auth
- **`/api/rerender` route** — `POST /api/rerender` (auth-gated) triggers an in-process HTML re-render and reloads the page; palette icon button in header
- **`/api/refetch` SSE route** — `GET /api/refetch` (auth-gated) spawns a full `steam-fetch` subprocess and streams live progress to the browser via Server-Sent Events; a modal overlay displays the log; only one fetch can run at a time (mutex lock)
- **Auth panel in header** — 🔑 (Login) button visible only when not authenticated, 🔓 (Logout) visible only when authenticated; icon-only with tooltip; re-render 🎨 and refetch ⬇ buttons shown only when authenticated

### Fixed

- **Duplicate news alerts in combined view** — when multiple alert rules matched the same news item, the combined view showed the article multiple times; deduplicated by `(appid, source_id)` pair in JS (fixes #30)
- **Epic source failure no longer marks games as removed** — when a source (e.g. Epic) fails during a fetch, games belonging to that source are excluded from the soft-delete reconciliation; `source_labels` is now a required field of the `GameSource` protocol so the CLI can enforce this without `getattr` fallbacks
- **`appendLog` JS SyntaxError** — unescaped newline in `'\n'` inside the sidecar JS string template broke the entire JS block
- **`UnicodeEncodeError` in refetch subprocess** — `steam-fetch` subprocess now inherits `PYTHONUTF8=1` in its environment to avoid cp1252 encoding errors on Windows
- **`UnicodeDecodeError` reading subprocess stdout** — `subprocess.Popen` now uses `encoding="utf-8"` when reading subprocess output instead of defaulting to the system locale
- **`_fetch_lock` not released on `load_config()` failure** — pre-flight config load is now inside the `try/finally` block so the mutex is always freed even if config parsing raises
- **Server binding on all interfaces** — `steam-serve` now binds to `127.0.0.1` by default instead of `0.0.0.0`; a new `--host` flag allows overriding for intentional LAN access
- **`Access-Control-Allow-Origin: *` on mutation API** — removed the wildcard CORS header from all JSON responses; mutations are only accessible from the same origin
- **Missing `aria-label` on icon-only buttons** — all icon-only header controls (re-render, refetch, login, logout) and card action buttons (mark-removed, reactivate, delete) now carry an `aria-label` matching their `title` tooltip for screen-reader accessibility
- **Re-render skipped when no `--steamid` configured** — `POST /api/refetch` no longer attempts to call `_rerender` with an empty Steam ID after a successful fetch; a warning is printed instead
- **Invalid token characters** — `steam-serve` now validates at startup that `--token` contains only alphanumeric characters and hyphens (`[\w\-]+`) and raises `ValueError` for tokens with forbidden chars (e.g. `;` or spaces that could corrupt the session cookie)

---

## [1.6.4] — 2026-03-22

### Fixed

- **Unknown games filter missed resolved games without details** — games with a valid Steam AppID but no `app_details` (e.g. delisted games like Dishonored - Definitive Edition) were tagged INCONNU but not caught by the unknown toggle filter; `data-unknown` attribute now also checks `status.badge == "unknown"`

---

## [1.6.3] — 2026-03-22

### Added

- **Unknown games toggle filter** — games with unresolved Steam AppIDs (synthetic appid ≥ 2B) are now hidden by default in both the library and alerts pages; a new toggle button in the filter panel lets users show/hide them; state is persisted in URL hash and localStorage
- **Unknown games in diagnostic page** — new section listing all unknown/unresolved games with name, source, external ID, and synthetic AppID; sorted alphabetically with a count badge
- **Cross-source duplicate cleanup** — `_cleanup_epic_duplicate_external_id` now catches duplicates across sources (e.g. owned + epic with same external_id), not just epic↔epic
- **Same-name duplicate cleanup** — new `_cleanup_epic_duplicate_name` rule removes synthetic-appid games whose name exactly matches a real-appid game (e.g. Death Stranding ×5)

---

## [1.6.2] — 2026-03-22

### Added

- **Epic "Production" name cleanup rule** — `_cleanup_epic_production_name` removes Epic games with sandbox names matching `^\w+ Production$` (e.g. "coffee Production", "boysenberry Production") and their `appid_mappings` entries
- **Epic duplicate external_id cleanup rule** — `_cleanup_epic_duplicate_external_id` removes duplicate Epic entries where both a real-appid and a synthetic-appid row exist for the same `external_id`; keeps the real-appid entry
- **Systematic Catalog API enrichment** — `EpicSource.discover_games()` now queries the Epic Catalog API for ALL library items (not just those missing titles), ensuring codename-only items (e.g. "BrilliantRose" → "Gone Home") get their real titles; `_extract_epic_title()` is kept as fallback only

### Fixed

- **Epic source failure no longer marks games as removed** — when a source (e.g. Epic) fails to connect during a fetch run, games belonging to that source are now excluded from the soft-delete reconciliation; they retain their current status instead of being incorrectly marked as removed

---

## [1.6.1] — 2026-03-22

### Added

- **Diagnostic page nav link** — library and alerts pages now include a 🔍 navigation link to the diagnostic page in their toolbars

### Fixed

- **Epic hex-ID cleanup rule** — existing games with hex catalog ID names (imported before hex-ID filtering was added) are now automatically cleaned up from the database on the next fetch run

---

## [1.6.0] — 2026-03-22

### Added

- **Diagnostic page** — new `steam_diagnostic.html` page generated alongside library and alerts pages; provides database summary stats, per-source game counts, AppID mapping table with search, Epic discovery statistics, and skipped items table with skip reasons
- **Diagnostic interactive filters** — stat cards on the diagnostic page are now clickable; clicking a card filters the mapping table to the corresponding status (resolved / unresolved / manual); combined with the existing text search
- **Epic hex-ID filtering** — games whose only name is a long hex catalog ID (e.g. `91eac4ac00304bcc…`) are now automatically filtered out during Epic library discovery; tracked as `SkippedItem(reason="hex_id")` and visible on the diagnostic page
- **Epic Catalog API enrichment** — batch title resolution via Epic's public catalog endpoint (`catalog-public-service-prod06.ol.epicgames.com`); items lacking a human-readable name are looked up in bulk (batches of 50) to retrieve their catalog title before falling back to the existing title chain
- **Epic library deduplication** — `discover_games()` now tracks seen game names and skips duplicates (e.g. multiple "Death Stranding" entries); tracked as `SkippedItem(reason="duplicate")`
- **Resolver word-prefix matching** — new `_is_word_prefix()` strategy in `_best_match()`: matches when the Epic name is a word-boundary prefix of the Steam name (e.g. "Control" → "Control Ultimate Edition"); includes sequel rejection to avoid false positives (e.g. "Arma 2" ≠ "Arma 3")
- **Resolver word-containment matching** — new `_is_word_contained()` strategy after prefix: matches when the Epic name is fully contained within the Steam name with word-boundary checks (e.g. "Ghost Recon Breakpoint" inside "Tom Clancy's Ghost Recon® Breakpoint")
- **Resolver edition-suffix stripping** — `_strip_edition()` removes common edition suffixes (GOTY, Definitive, Ultimate, Director's Cut…) and retries Steam search when the original name returns no suitable match
- **Resolver year normalization** — `_shorten_year()` converts 4-digit years to 2-digit (e.g. "Farming Simulator 2022" → "Farming Simulator 22") and retries search as a last resort
- **Version display** — `--version` flag on all CLI commands; startup banner prints `SteamPulse vX.Y.Z` at launch
- 378 tests total

### Fixed

- **Epic refresh token lost on crash** — credentials (especially rotated Epic `refresh_token`) are now persisted immediately after game discovery, before the enrichment phase; previously they were only saved at the very end of the pipeline, so a crash during fetch/render would lose the new single-use token
- **Epic games still named "Live" after fix** — sandbox label filtering (`_SANDBOX_LABELS`) now applies to ALL title fields (`catalogItem.title`, `productName`), not just `sandboxName`; the `appName` fallback is also rejected when it matches a sandbox label

---

## [1.5.0] — 2026-03-21

### Added

- **Alerts page UX redesign** — differentiated click zones (game image/name → store page, news title/body → news URL, checkmark → mark read), "Rule / Game" dual-grouping view with two levels of collapsible sections, autocomplete search filtered to visible games, search-clear buttons (×), font size controls (A−/A+, persisted in localStorage), larger game thumbnails (120×56), responsive card sizing
- **Mobile UX improvements** — auto-hide toolbar (slides up on scroll down, reappears on scroll up), compact header (hidden logo, smaller stats), full-width search, smaller buttons/controls on both library and alerts pages
- **Automatic DB cleanup on fetch** — extensible rule-based cleanup system (`Database.run_cleanup()`); runs before game discovery to purge stale data. First rule: remove Epic games incorrectly named "Live" and their `appid_mappings`
- 13 new tests (295 passed, 2 skipped — POSIX-only config-path tests on Windows)

### Fixed

- **Epic games displayed as "Live"** — `sandboxName` (a deployment environment label) was incorrectly used as the game title; replaced with a robust fallback chain: `catalogItem.title` → `productName` → `sandboxName` (only if not a known environment label) → `appName`

---

## [1.4.0] — 2026-03-21

### Added

- **Configurable alerts system** (`steam_tracker/alerts.py`) — replaces the standalone news page with a rule-based alert engine. Six default rules shipped via `steam-setup`:
  - `all_news` — all news items (replaces the old news page)
  - `price_drop` — price decreased
  - `release_1_0` — game left Early Access (`release_date_is_early_access` went from `True` to `False`)
  - `review_bomb` — Metacritic score dropped by ≥ 10 points
  - `major_update` — `buildid` changed (silent update detected via SteamCMD)
  - `new_dlc` — `dlc_appids` list changed (new DLC released)
- **`steam_alerts.html` replaces `steam_news.html`** — new self-contained HTML dashboard with dark CSS, 3 view modes (by rule / by game / combined), read/unread tracking via `localStorage`, mark individual or mark-all-read
- **Alert rules in TOML** — `[[alerts]]` sections in `config.toml`; two rule types: `news_keyword` (match news titles/tags) and `state_change` (detect field diffs)
- **SteamCMD API** (`steam_tracker/steamcmd_api.py`) — fetches `buildid`, `timeupdated`, depot sizes, branch names from `api.steamcmd.net` (free, no auth); enables detection of silent updates
- **Field history** — `field_history` DB table tracking all `app_details` changes across fetches; enables retroactive alert creation and change-based rules
- **Automatic backfill** — after each fetch, new or changed alert rules are automatically evaluated against the full field history; no manual CLI flag needed
- **New Store API fields** — `contents` (full article body), `dlc_appids`, `controller_support`, `required_age` now parsed and stored
- **New DB tables** — `field_history` and `alerts` with additive migrations; `upsert_app_details()` now returns `list[FieldChange]` for downstream alert evaluation
- **30 new tests** — 21 in `test_alerts.py`, 9 in `test_steamcmd_api.py`
- **Accordion sections** — in "By rule" and "By game" views, alerts are grouped under collapsible section headers with animated chevron (❯); all sections start collapsed by default
- **Toggle all button** — "Expand all / Collapse all" button to open or close every accordion group at once
- **Group search** — real-time search field in the toolbar to filter section headers by name (visible only in grouped views)
- **Alerts toolbar redesign** — search box, sort dropdown (date, name, playtime, Metacritic), view-mode buttons (combined/by-rule/by-game), group controls, filter toggle with badge, reset button, mark-all-read
- **Full filter panel on alerts page** — 7 filter groups (Status, Store, Collection, News type, Playtime, Metacritic, Recent update) shared with the library page
- **Cross-page filter persistence** — Store and Collection filter state is carried between Library ↔ Alerts via URL hash, `window.name`, and `localStorage`
- **Build ID badge** — alert cards display a `build XXXXX` badge when the game has a non-zero `buildid` (useful for silent update detection)

### Changed

- **Navigation**: Library ↔ Alerts (2 pages) — the 🗞 News nav link is replaced by 🔔 Alerts
- **`cmd_fetch` / `cmd_run`** — `AlertEngine` is wired into the fetch pipeline; alerts are generated on each game result based on configured rules
- **`cmd_render`** — outputs `steam_alerts.html` instead of `steam_news.html`
- **`SteamFetcher`** — merges SteamCMD metadata (`buildid`, `timeupdated`, `depot_sizes`, `branches`) via `model_copy(update={...})`
- **Wizard** — writes `DEFAULT_ALERT_RULES` to `config.toml` on first setup

### Fixed

- **Alert rules lost on credential save** — `save_cli_credentials()` now preserves existing `[[alerts]]` rules when rewriting `config.toml` (previously, updating a credential erased the alerts section)

### Removed

- **`steam_news.html`** — replaced by `steam_alerts.html`
- **`make_news_row()`, `generate_news_html()`, `write_news_html()`** — removed from `renderer.py`; replaced by `make_alert_card()`, `generate_alerts_html()`, `write_alerts_html()`

---

## [1.3.0] — 2026-03-19

### Changed (`aspect-ratio: 460 / 215`) instead of a fixed 80 px height; images fill the card frame without stretching or squashing (may be cropped when their aspect ratio differs).
- **Card metadata** — AppID (`#appid`) removed from the visible card body; it is still available as the `data-appid` HTML attribute.
- **News section** — hidden entirely when a game has no recent news, reclaiming the footer space on the card.
- **News overlay** — the news accordion now expands as a `position: absolute` overlay below the card, leaving the grid layout undisturbed; all other cards are dimmed (opacity 0.3) and blurred (blur 1.5 px, scale 0.975); only one card can be expanded at a time; clicking outside collapses it.
- **Metacritic badge tooltip** — hovering the MC badge shows a popover with the score /100 and a quality label: *Favorable* (≥ 75), *Mixed* (50–74), *Negative* (< 50).
- **Filter button tooltips** — hovering any non-trivial filter button shows a short explanatory tooltip via `data-tooltip` CSS; available in English and French.
- **Mobile filter panel** — on screens ≤ 600 px, the filter panel opens as a full-screen fixed overlay (instead of a small dropdown) with a sticky "Filters ✕" close button.

---

## [1.2.0] — 2026-03-17

### Added — single self-contained image bundling nginx (serves generated HTML pages) and a configurable scheduler loop (default interval: 4 hours). Infrastructure files:
  - `docker/Dockerfile` — Python 3.13-slim + nginx + supervisord
  - `docker/nginx.conf` — serves `/data` on port 80; blocks direct access to `.db` files
  - `docker/supervisord.conf` — manages nginx + scheduler as two supervised processes
  - `docker/entrypoint.sh` — mounts a user-provided `config.toml`, creates a loading placeholder page, then starts supervisord
  - `docker/scheduler.sh` — fetch loop using `--config /run/steampulse/config.toml`; no secrets in process args
  - `docker-compose.yml` — ready-to-use Compose file distributed with each GitHub release; bind-mounts `./config.toml` (read-only) and `./data` (database + HTML output); suitable for Synology NAS and any Docker engine
  - `.dockerignore` — keeps the build context lean
  - `.github/workflows/docker.yml` — publishes image to GHCR (`ghcr.io/davidp57/steampulse`) on every `v*` tag and `main` push (`latest` tag); `develop` branch pushes produce a `:develop` tag for pre-release testing
- **`docker-compose.yml` in GitHub releases** — the CI `build.yml` workflow now attaches `docker-compose.yml` as a release asset, so users can `curl` or download it directly without cloning the repo

### Changed

- **Filter UI — store vs. collection** — The single mixed "Source" filter is replaced by two distinct filter groups on both the library and news pages:
  - **Store** (multi-select toggle, OR logic): `🎮 Steam` / `⚡ Epic` — both active by default; the last active store cannot be deactivated.
  - **Collection** (single-select): `All` / `Owned` / `🎁 Wishlist` / `👁 Followed`.
  - The two groups are combined with AND: a game is shown only if its store is active **and** its collection status matches.
  - `data-source` HTML attribute on cards and news rows is replaced by `data-store` + `data-lib-status` (derived from `OwnedGame.source` in the renderer; no model change).
  - URL hash keys change from `source=…` to `stores=…` (comma-separated, omitted when all active) + `lib=…`.

### Added

- **TOML config file support** (`steam_tracker/config.py`) — Automatically loads `~/.config/steampulse/config.toml` (Linux/macOS) or `%APPDATA%\steampulse\config.toml` (Windows). All credentials and settings can be stored there; CLI flags still take precedence. Prints `✔ Config loaded from …` / `✔ Config written to …` messages. New CLI flag `--config <path>` to use a custom file.
- **Interactive setup wizard** (`steam_tracker/wizard.py`, `steam-setup`) — Guides the user step by step through Steam credentials, optional Epic Games OAuth2 flow (including automatic browser launch, auth-code exchange, and automatic refresh token storage), optional Twitch/IGDB credentials, and optional settings. Writes the config file on confirmation. Available as `steam-setup` command or via `steampulse --setup` / `steam-fetch --setup`.
- **Auto-wizard on first run** — If no config file exists and no `--key`/`--steamid` flags are present, the wizard starts automatically instead of failing with an error.
- **CLI save-back** — Credentials passed directly on the command line are automatically persisted to the config file after a successful run, so they need not be repeated.
- **`epic_auth_with_refresh()`** in `steam_tracker/epic_api.py` — Renews an Epic session from a saved refresh token (valid 30 days, automatically renewed on each use). Used by the wizard and `EpicSource` for all subsequent runs after first login.
- **18 tests** in `tests/test_wizard.py` covering Steam-only flow, cancellation, custom settings, Twitch credentials, Epic refresh token flow, Epic auth failure resilience, browser launch, URL display, and pre-fill from existing config.
- **26 tests** in `tests/test_config.py` covering `get_config_path`, `load_config`, `write_config`, and `save_cli_credentials` (including credential-vs-settings distinction and `_explicit_keys` logic).

### Changed

- **`--key` and `--steamid` are no longer required flags** — They are now optional (`required=False`) in `SteamSource.add_arguments()`. Missing values are caught post-parse with a helpful error message directing the user to `steam-setup`.
- **`cmd_render` `--steamid` is no longer required** — Same pattern: missing value is caught post-parse.
- **`cmd_fetch`, `cmd_render`, `cmd_run`** — All now pre-parse `--config` and `--setup`, load the config file, apply it via `parser.set_defaults()`, and save changed credentials back after a successful run.

- **`GameSource` plugin architecture** (`steam_tracker/sources/`) — `GameSource` runtime-checkable Protocol; `get_all_sources()` registry; `SteamSource` plugin (owned library, wishlist, followed games) extracted from `cli.py`. New source plugins can be added without touching the CLI.
- **Epic Games Store source plugin** (`steam_tracker/sources/epic.py`) — `EpicSource` discovers games from an Epic Games account via OAuth2 authorization code (first login) or a persisted refresh token (subsequent runs).
- **Steam AppID resolver system** (`steam_tracker/resolver.py`) — Chain-of-responsibility pattern: `SteamStoreResolver` (fuzzy name matching via Steam Store Search API) and `IGDBResolver` (IGDB + Twitch OAuth). First successful result wins.
- **`SYNTHETIC_APPID_BASE`** constant in `steam_tracker/models.py` — Sentinel value (`2_000_000_000`) used to tell real Steam AppIDs from hash-based placeholders assigned to unresolved Epic games.
- **`appid_mappings` table** in the database — Caches resolved external→Steam AppID mappings. Manual entries (`manual=True`) are protected from automatic overwrite.
- **`external_id` field** on `OwnedGame` — Identifies games from non-Steam sources (e.g. `"epic:<catalogItemId>"`).
- **Epic Games API module** (`steam_tracker/epic_api.py`) — OAuth2 token exchange (authorization code + device auth flows) and paginated library retrieval via Epic’s undocumented API.
- **Epic display in HTML dashboards** — Source filter buttons “👁 Followed” and “🎮 Epic” on both library and news pages. Epic cards show a “🎮 Epic” store hint. Playtime label adapts to source (Wishlist / Followed / Epic).
- **New CLI flags**: `--epic-auth-code`, `--epic-refresh-token`, `--epic-account-id`, `--twitch-client-id`, `--twitch-client-secret` (replaces `--epic-device-id` / `--epic-device-secret`: Epic's `deviceAuths` endpoint is restricted; refresh tokens are more reliable and require no server-side permission).
- **UX: per-game progress during Epic AppID resolution** — Inline `[N/total] Game Title` indicator updated in place via `\r`, followed by a resolved/unresolved summary.
- **Epic i18n keys** (`cli_epic_*`) — Authentication, library count, resolution progress and summary in English and French.
- **33 tests** in `tests/test_sources.py` (18 SteamSource + 15 EpicSource).
- **17 tests** in `tests/test_epic.py` covering EpicSource protocol conformance, CLI arguments, auth flows, library discovery, and resolver integration.
- **14 tests** in `tests/test_resolver.py` covering SteamStoreResolver, IGDBResolver, fuzzy matching, and resolver chain.
- **9 tests** in `tests/test_cli.py` covering `_build_enrichment_queue` including boundary values and deduplication.
- **9 new tests** in `tests/test_db.py` covering `appid_mappings` CRUD, manual mapping protection, `external_id` persistence, and Epic source priority.
- **Bilingual documentation** — `docs/en/user-guide.md` and `docs/fr/user-guide.md` updated with Epic prerequisites section, all new CLI flags, source filter docs, and FAQ entry.

### Changed

- **`cli.py`** — Enrichment filter extracted into `_build_enrichment_queue()` (pure, testable helper). Games with a synthetic appid (`≥ SYNTHETIC_APPID_BASE`) are excluded from the Steam Store enrichment pass; resolved Epic games (real Steam AppID) are correctly included.
- **`db.py`** — Source priority treats `"epic"` at the same level as `"owned"`. `upsert_game` persists the new `external_id` column.
- **`sources/__init__.py`** — `get_all_sources()` returns `[SteamSource(), EpicSource()]`.
- **`README.md`** — Added “Multi-store” feature line (EN + FR); test count updated to 168.

### Fixed
- **Incremental DB writes during fetch** — `SteamFetcher` now accepts an `on_result` callback (`ResultCallback` type) called as each future completes; `cmd_fetch` and `cmd_run` write each game to the database immediately rather than buffering all results until the end. This means the database is populated progressively and a Ctrl+C still saves partial results.
- **Docker data directory** — switched from a named Docker volume to a bind mount (`./data:/data`) so the SQLite database and generated HTML files are directly accessible on the host filesystem (e.g. NAS File Station).
- **Wizard skipped on `--help` / `-h`** — the auto-wizard trigger now checks for `--help`/`-h` in `sys.argv` and returns early, preventing the wizard from interrupting `steampulse --help`.
- **Wizard always exits after completion** — whether invoked explicitly (`--setup`) or automatically (no config found), the wizard now always prints the config path and exits cleanly with `sys.exit(0)` rather than continuing to a fetch.- Resolved Epic games (with a real Steam AppID) are now correctly enriched via the Steam Store API; previously the `external_id` presence check incorrectly excluded them.
- Epic game display names now use `sandboxName` (human-readable title, e.g. “Gone Home”) instead of the internal `appName` codename (e.g. “Flier”).
- Epic OAuth login URL in documentation had a truncated `clientId` (missing trailing `a`).

---

## [1.1.0] — 2026-03-15

### Added

- **Toolbar UX redesign** — Two-layer toolbar: compact sticky main row (`Search · Sort · ⚙ Filtres · Reset · View · Count · Nav`) + collapsible filter panel with 6 labeled groups (Statut, Source, Type news, Temps de jeu, Metacritic, Màj récente). Filter badge on toggle button shows count of active filters. Panel auto-opens on page load when URL hash contains active filters.
- **"Màj récente" filter** — New filter group in the panel (Tous / 2 jours / 5 jours / 15 jours / 30 jours). Shows only games that received a patchnote in the selected time window, using `data-last-patch-ts`. Persisted in URL hash (`recent=` key).
- **News page toolbar** — Same two-layer collapsible structure applied to news page (Statut + Type news groups).
- **Multilingual support (i18n)** — All UI strings (HTML pages + CLI output) are now translatable. Ships with English (`en`) and French (`fr`) translations. The active language is selected automatically from the system locale and can be overridden with `--lang <code>`.
- **`--lang` option** on both `steampulse` and `steam-render` — force the output language independently of the system locale (e.g. `--lang fr`).
- **17 new renderer tests** — coverage for `_parse_release_ts`, `make_news_row`, `generate_news_html`, `write_html`, `write_news_html`, and news timestamp data-attributes (`data-last-patch-ts`, `data-last-other-ts`).

### Changed

- **`_apply_html_t`** now scans templates dynamically with a regex instead of maintaining a hardcoded key list — new i18n keys are picked up automatically.
- **`make_card` / `make_news_row`** default translator now auto-detects the system locale instead of always falling back to English.

---

## [1.0.1] — 2026-03-15

### Fixed

- **Packaging** — declare `steam_tracker` as the wheel package in `pyproject.toml` so that `pip install` (and the CI) can resolve the package correctly when the project name differs from the source directory

---

## [1.0.0] — 2026-03-14

### Added

- **`steampulse`** all-in-one CLI command — fetch + render in a single step
- **Standalone Windows executable** (`steampulse.exe`) built with PyInstaller, distributed via GitHub Releases
- **News tag display** — each news item shows a tag badge (`PATCHNOTES` in green, other tags in grey)
- **Tag filter on news page** (`📋 Patch notes` / `📰 News`) — independent of the status filter
- **Tag filter on library page** — filters the news list inside each card, updates the last-news date to match the selected type, and feeds the "Last update" sort
- **Last-news date per tag** — `📰` date in each card reflects the most recent news matching the active tag filter
- **Bilingual README** (🇬🇧 English + 🇫🇷 Français in a single file)
- **Bilingual user guides** restructured around `steampulse.exe` as the primary entry point (separate-step commands moved to "Advanced usage" section)
- **CI workflow** (`ci.yml`) — quality gate on Windows, Python 3.11 / 3.12 / 3.13
- **Build workflow** (`build.yml`) — produces `steampulse.exe` on tag push; uploads to GitHub Release

### Changed

- Default entry point is now `steampulse` (fetch + render); `steam-fetch` / `steam-render` kept for advanced use
- Sort by "Dernière MàJ" now uses the tag-filtered timestamp when a tag filter is active
- News items in card drop-down are filtered in sync with the active tag button

---

## [0.1.0] — 2026-03-14

### Added

- **`steam-fetch`** CLI command — fetches owned games, wishlist and followed games from the Steam Web API
- **`steam-render`** CLI command — generates two static offline HTML pages:
  - `steam_library.html` — filterable/sortable card-based library view
  - `steam_news.html` — chronological news feed across all games
- **Multi-threaded fetcher** (`SteamFetcher`) with a thread-safe `RateLimiter` (configurable via `--workers` and `--rate-limit`)
- **Smart cache** — app details skipped for already-cached games; news automatically refreshed after `--news-age` hours (default: 24 h)
- **`--refresh`** flag to force a full re-fetch ignoring the cache
- **Wishlist support** via `IWishlistService/GetWishlist/v1` (requires API key)
- **Followed games** support via `--followed` opt-in flag
- **`source` field** on games (`"owned"` / `"wishlist"` / `"followed"`) with source-priority upsert (owned > wishlist > followed)
- **Source filter** in the library HTML (🎮 All · Owned · 🎁 Wishlist)
- **Last news date** displayed in each game card
- **News page** (`steam_news.html`) with search, status filter, and live result counter
- **Graceful Ctrl+C** — in-flight fetch tasks are cancelled cleanly; already-saved data is preserved
- **Additive DB migrations** — new columns added via `ALTER TABLE` for compatibility with existing databases
- **59 unit tests** — `api`, `db`, `fetcher`, `renderer` modules covered with `pytest` + `responses`
- **ruff** linting and **mypy strict** type checking enforced
- Bilingual documentation (EN + FR): user guide and developer guide

### Technical notes

- Python 3.11+, Pydantic v2, SQLite WAL mode, `ThreadPoolExecutor`
- HTTP 403/404 on news/details endpoints logged at DEBUG (not WARNING)
- `pyproject.toml`-based packaging with `hatchling`

[Unreleased]: https://github.com/davidp57/SteamPulse/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/davidp57/SteamPulse/compare/v1.0.1...v1.1.0
[1.0.1]: https://github.com/davidp57/SteamPulse/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/davidp57/SteamPulse/compare/v0.1.0...v1.0.0
[0.1.0]: https://github.com/davidp57/SteamPulse/releases/tag/v0.1.0
