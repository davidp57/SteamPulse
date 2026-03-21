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

---

## 🔵 Planned / Not yet started

### SteamCMD API integration
- **SteamCMD API** (`steamcmd_api.py`) — fetch `buildid`, `timeupdated`, depot sizes, branch names from `api.steamcmd.net` (free, no auth); detect silent updates and version branches
- **New Store API fields** — parse `dlc` list, `controller_support`, `required_age` (already in response, currently ignored)
- **Field history** — `field_history` DB table tracking ALL `app_details` changes across fetches; enables retroactive alert creation
- New columns in `app_details` via additive migrations; all changes tracked automatically

### Configurable Alerts
- **Alert rules engine** (`alerts.py`) — configurable rules in TOML (`[[alerts]]`); two types:
  - `news_keyword`: match news titles/tags by keywords (e.g. "1.0 Release", "Version Update")
  - `state_change`: detect field diffs (e.g. `buildid` changed, `price_final` decreased, `metacritic_score` appeared, `dlc_appids` changed)
- **Default rules** shipped in TOML via `steam-setup`; "All News" is the only hardcoded builtin rule
- **`steam_alerts.html` replaces `steam_news.html`** — news page becomes the "All News" rule; 3 view modes (by rule / by game / combined); filter by rule, status, store
- **Read/unread** via `localStorage` (no server needed); mark individual, per-rule, or all; unread badge in nav
- **Backfill** — `--backfill-alerts` CLI flag to retroactively generate alerts from existing `field_history`
- Navigation: Library ↔ Alerts (2 pages)

### Manual AppID mappings CLI
- Interface to add/edit manual `appid_mappings` entries (e.g. `steam-fetch --add-mapping epic:Flier 1234567`)
- Useful for games that fail automatic resolution (e.g. Epic exclusives with no Steam page)
- `manual=True` entries already protected in DB — just needs a CLI surface

### Additional store plugins
- **GOG** — GOG Galaxy API or `gogdl` approach
- **Xbox Game Pass** — Xbox / Microsoft Store API
- **Amazon Prime Gaming** — library discovery
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
