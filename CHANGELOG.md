# Changelog

All notable changes to SteamPulse will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).  
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

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
