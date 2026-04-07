# feat: GOG + Game Pass sources, web config UI, store filters & multiselect toggle

This PR adds two new game sources (GOG Galaxy and Xbox PC Game Pass), a browser-based configuration page, and several UI improvements to the library and alerts dashboards.

## Key changes

- **GOG Galaxy source** (`gog_api.py`, `sources/gog.py`) — OAuth2 browser auth via `steam-setup` wizard; refresh token stored in TOML; games tagged `gog`; Steam AppID resolved via the existing resolver chain
- **Xbox PC Game Pass source** (`gamepass_api.py`, `sources/gamepass.py`) — public Microsoft catalog API, no auth required; `--game-pass` flag; games tagged `gamepass`
- **Web configuration page (`/config`)** — served by `steam-serve`; lets users edit all credentials and settings from a browser form; credential fields are masked (`● ● ●`); accessible without auth in bootstrap mode (no `serve_token` set)
- **`POST /api/config` / `GET /api/config`** — save/read config as JSON; masked `***` values are ignored on save to protect existing secrets
- **Auto-restart on token change** — sidecar exits cleanly when `serve_token` changes from the web UI; browser polls then redirects to `/login`
- **Fetch-progress bandeau** — live top banner on the library page showing fetch `idx/total` + game name (polling `/api/status` every 3 s); reloads page on completion
- **`GET /api/status`** — public endpoint for live fetch progress state
- **Store filter buttons for GOG & Game Pass** — `🌌 GOG` and `🎯 Game Pass` filter buttons added to both library and alerts filter panels
- **Store multiselect toggle** — "multi" checkbox next to the Store filter label; unchecked (default) = exclusive selection; checked = individual toggle; state persisted in `localStorage` and URL hash
- **Config icon in auth dock** — ⚙ link to `/config` added to the sidecar auth panel; visible whenever `steam-serve` is running

## Testing

- 536 tests pass (2 skipped); coverage 82%
- New test files: `tests/test_gog_api.py` (10 tests), `tests/test_gamepass_api.py` (7 tests)
- Extended: `tests/test_server.py` (+45 tests for config routes and status endpoint), `tests/test_sources.py` (+GOG and GamePass source tests), `tests/test_config.py`, `tests/test_wizard.py`
- ruff: no issues; mypy: no issues (24 source files, strict mode)

## Docs

- `docs/en/user-guide.md` and `docs/fr/user-guide.md` — GOG/GamePass setup, `--game-pass` flag, `/config` page usage
- `docs/en/developer-guide.md` and `docs/fr/developer-guide.md` — new modules, updated source registry table, GogSource / GamePassSource sections
