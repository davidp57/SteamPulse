# SteamPulse — Roadmap

## ✅ Done

### v1.0.0 — Core
- `steampulse` CLI (fetch + render in one step)
- Standalone Windows EXE via PyInstaller
- GitHub Actions CI/CD (lint + types + tests + release)

### v1.0.1 — Packaging fix
- Correct `pyproject.toml` wheel package declaration

### v1.1.0 — UI & i18n
- Two-layer collapsible toolbar (library + news pages)
- "Màj récente" filter (last-patch-ts window: 2/5/15/30 days)
- Multilingual support (EN / FR) — `--lang` flag
- URL hash persistence for all filters

### v1.2.0 — Multi-store (Epic Games)
- **`GameSource` plugin architecture** — `sources/` package, runtime-checkable Protocol, `get_all_sources()` registry; new stores can be added without touching `cli.py`
- **Epic Games Store source** (`EpicSource`) — OAuth2 auth (authorization code on first login, device credentials for subsequent headless runs)
- **Steam AppID resolver chain** (`resolver.py`) — `SteamStoreResolver` (Steam Store Search + fuzzy matching) → `IGDBResolver` (Twitch OAuth + IGDB); first hit wins; results cached in `appid_mappings` DB table
- **`appid_mappings` table** — caches external→Steam AppID resolutions; `manual=True` entries are protected from automatic overwrite
- **`external_id` field on `OwnedGame`** — identifies non-Steam games (e.g. `"epic:<catalogItemId>"`)
- **Epic display in HTML dashboards** — "🎮 Epic" filter button, store badge on cards, context-aware playtime label
- **New CLI flags**: `--epic-auth-code`, `--epic-device-id`, `--epic-account-id`, `--epic-device-secret`, `--twitch-client-id`, `--twitch-client-secret`
- **UX**: per-game progress indicator during Epic AppID resolution + resolved/unresolved summary

### v1.3.0 — Config file, wizard & UI polish
- **TOML config file** — stdlib `tomllib`; platform-specific path (`%APPDATA%\steampulse\config.toml` / `~/.config/steampulse/config.toml`); CLI flags override config
- **Interactive setup wizard** (`steam-setup`) — step-by-step credential setup; OAuth2 Epic flow built-in; auto-saves config
- **Card image aspect ratio** — native Steam 460×215 (`aspect-ratio: 460 / 215`); never stretched or squashed
- **News overlay** — `position:absolute` overlay below the card; single-open; outside-click closes; grid dims/blurs
- **Metacritic badge tooltip** — score/100 + quality label (Favorable/Mixed/Negative), localized EN/FR
- **Hover tooltips on all card elements** — badge, developer, platform icons, release date, news date, playtime, price; all via `data-tooltip` CSS
- **Filter button tooltips** — 20 keys × EN + FR
- **Mobile filter panel** — full-screen overlay on ≤ 600 px with close button
- **i18n** — 28 new tooltip keys (EN + FR)
- 226 tests total

### v1.4.0 — SteamCMD, Alerts & Field History
- **SteamCMD API** (`steamcmd_api.py`) — fetches `buildid`, `timeupdated`, depot sizes, branch names from `api.steamcmd.net` (free, no auth); detects silent updates
- **New Store API fields** — `contents`, `dlc_appids`, `controller_support`, `required_age` parsed and stored
- **Field history** — `field_history` DB table tracking all `app_details` changes across fetches; enables retroactive alert creation
- **Configurable alert rules engine** (`alerts.py`) — `[[alerts]]` rules in TOML; two types: `news_keyword` (match news titles/tags by keywords) and `state_change` (detect field diffs: `buildid` changed, `price_final` decreased, `metacritic_score` appeared, `dlc_appids` changed)
- **6 default rules** shipped via `steam-setup`: All News, Price Drop, Release 1.0, Review Bomb, Major Update, New DLC
- **`steam_alerts.html` replaces `steam_news.html`** — 3 view modes (by rule / by game / combined); read/unread via `localStorage`; mark individual, per-rule, or all
- **Accordion sections** — collapsible groups in "By rule" and "By game" views with animated chevron; toggle all button; group search field
- **Full filter panel on alerts page** — 7 shared filter groups (Status, Store, Collection, News type, Playtime, Metacritic, Recent); cross-page persistence via URL hash + `localStorage`
- **Build ID badge** on alert cards for silent update detection
- **Automatic backfill** — after each fetch, alert rules are re-evaluated against full field history (no manual flag needed)
- Navigation: Library ↔ Alerts (2 pages)
- 271 tests total

### v1.5.0 — Alerts UX, Epic title fix & DB cleanup
- **Alerts page UX redesign** — differentiated click zones, dual-grouping view (Rule / Game), autocomplete search, font size controls, larger thumbnails, responsive sizing
- **Mobile UX improvements** — auto-hide toolbar, compact header, full-width search on both pages
- **Automatic DB cleanup on fetch** — extensible rule-based cleanup (`Database.run_cleanup()`); first rule removes Epic games incorrectly named "Live"
- **Epic title fix** — robust fallback chain (`catalogItem.title` → `productName` → filtered `sandboxName` → `appName`)
- 295 tests total

### v1.6.2 — Epic data quality
- **Epic "Production" name cleanup rule** — removes sandbox names matching `^\w+ Production$`
- **Epic duplicate external_id cleanup rule** — removes synthetic-appid duplicates when real-appid entry exists
- **Systematic Catalog API enrichment** — all Epic library items are now sent to the Catalog API for authoritative title resolution; `_extract_epic_title()` kept as fallback only
- **Unknown games toggle filter** — games with unresolved AppIDs (≥ 2B) hidden by default in library and alerts; toggle to show/hide; persisted in URL hash + localStorage
- **Unknown games diagnostic section** — unknown games listed in diagnostic page with name, source, external ID, AppID
- **Cross-source duplicate cleanup** — duplicate external_id detection works across sources (owned + epic)
- **Same-name duplicate cleanup** — new `_cleanup_epic_duplicate_name` rule removes synthetic duplicates matching real games by name
- **Unknown filter covers delisted games** — resolved games without `app_details` (delisted from Steam Store) are now correctly caught by the unknown toggle
- 406 tests total

### v1.6.1 — Post-deployment fixes & availability tracking
- **Diagnostic page nav link** — 🔍 link added to library and alerts page toolbars
- **Epic hex-ID cleanup rule** — automatic cleanup of existing hex-ID games from the database
- **Date-added tracking** — `time_added` column records first-seen timestamp per game; sort by date added in library dashboard; cards display ➕ date for newly discovered games; all card dates now `dd/mm/yy`
- **Soft-delete for removed games** — games disappearing from all sources are auto-tagged with `removed_at`; reappearing games are automatically reactivated; `--mark-removed` and `--delete` CLI flags for manual control
- **Availability filter** — new filter group in library page (Active / All / Removed); removed cards dimmed with badge
- 401 tests total

### v1.6.0 — Diagnostic page, Epic enrichment & resolver improvements
- **Diagnostic page** — `steam_diagnostic.html` with database stats, per-source game counts, AppID mapping table, Epic discovery stats, and skipped items table
- **Diagnostic interactive filters** — clickable stat cards to filter the mapping table by status (resolved / unresolved / manual)
- **Epic hex-ID filtering** — automatic filtering of hex catalog IDs during Epic library discovery
- **Epic Catalog API enrichment** — batch title resolution via Epic's public catalog endpoint (batches of 50)
- **Epic library deduplication** — duplicate game name detection and skip tracking
- **Resolver word-prefix matching** — `_is_word_prefix()` with sequel rejection
- **Resolver word-containment matching** — `_is_word_contained()` with word-boundary checks
- **Resolver edition-suffix stripping** — `_strip_edition()` removes GOTY, Definitive, Ultimate, etc.
- **Resolver year normalization** — `_shorten_year()` converts 4-digit to 2-digit years
- **Epic refresh token persistence** — credentials saved immediately after game discovery
- **Sandbox label filtering hardened** — `_SANDBOX_LABELS` applied to all title fields
- **Version display** — `--version` flag; startup banner prints version at launch
- 378 tests total

### v2.1.0 — New stores + web configuration
- **GOG Galaxy source** (`GogSource`) — OAuth2 browser flow via `steam-setup` wizard; refresh token persisted in TOML; games tagged `gog`; enriched via Steam AppID resolver chain
- **Xbox PC Game Pass source** (`GamePassSource`) — public Microsoft catalog API; no authentication required; `--game-pass` flag; games tagged `gamepass`
- **Web configuration page (`/config`)** — browser form served by `steam-serve` for editing all credentials and settings; accessible without auth in bootstrap mode; credential fields shown as masked placeholders to prevent accidental exposure
- **`POST /api/config`** — saves submitted config to TOML; ignores masked `***` values to protect existing secrets
- **`GET /api/config`** — returns current config as JSON with all credentials masked
- **Auto-restart on token change** — sidecar cleanly exits when `serve_token` changes from the web UI; supervisord restarts the process; browser polls then redirects to `/login`
- **Fetch-progress bandeau** — live top banner on the library page showing fetch `idx/total` + game name; reloads page on completion
- **`GET /api/status`** — public endpoint for live fetch progress state
- 536 tests total

---

### v2.0.0 — Sidecar server & self-hosted mode
- **`steam-serve` sidecar server** — lightweight stdlib HTTP server serving HTML dashboards from a local folder
- **Interactive action buttons** — ⛔ / ↩️ / 🗑️ on library cards for soft-delete, reactivation, and hard-delete (shown only when sidecar is running; graceful degradation otherwise)
- **Cookie-based authentication** — `--token` flag enables auth mode; `HttpOnly`/`SameSite=Strict` session cookie; timing-safe token comparison
- **`/api/rerender`** — in-process HTML re-render triggered from the UI
- **`/api/refetch` SSE** — streams live fetch progress to the browser; only one fetch runs at a time
- **Auth panel in header** — login / logout buttons, re-render and refetch buttons (auth-only)
- **Soft-delete for removed games** — `removed_at` timestamp instead of hard-delete; reappearing games auto-reactivated; `--mark-removed` and `--delete` CLI flags
- **Availability filter** — Active / All / Removed filter group in library page; removed cards dimmed with badge
- **Date-added tracking** — `time_added` column; "Sort by date added" option; ➕ date shown on newly discovered cards
- **Short date format** — all card dates now `dd/mm/yy`
- **`source_labels` in `GameSource` protocol** — required field protects games from false soft-delete when their source fails
- **Duplicate news deduplication in combined view** — `(appid, source_id)` pair dedup in JS (fixes #30)
- 473 tests total

---

## 🔵 Planned / Not yet started
- Interface to add/edit manual `appid_mappings` entries (e.g. `steam-fetch --add-mapping epic:Flier 1234567`)
- Useful for games that fail automatic resolution (e.g. Epic exclusives with no Steam page)
- `manual=True` entries already protected in DB — just needs a CLI surface

### Additional store plugins
- **Amazon Prime Gaming** — library discovery (no viable public API identified yet)
- Plugin architecture is already in place; adding a store = new `sources/<store>.py` file

### Collections
- User-defined groups to organize games across stores and statuses (e.g. "À finir", "Co-op avec amis", "Abandonné")
- Collections stored in the DB (`collections` and `collection_games` tables — additive migration)
- CLI surface to manage collections: `steam-fetch --add-to <collection> <appid|name>`, `--remove-from`, `--list-collections`
- HTML dashboard: collection filter group alongside Store / Collection status filters; a game can belong to multiple collections (multi-select, OR logic)
- Collections exported as part of the generated HTML (no server required)

---

## 💡 Ideas (not committed)

- Game price history tracking (store prices as time series)
- Export to CSV / JSON
- **Per-game news timeline** — dedicated view (or expandable panel on the card) showing the full update history for a single game: chronological list of patch notes and news entries, each with its date, title, type tag (patch note / news), and a direct link to the article; useful to quickly assess how actively a game is maintained
