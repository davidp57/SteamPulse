# SteamPulse — Copilot Instructions

## Project Overview

**SteamPulse** is a CLI tool that fetches a user's Steam library, wishlist, and followed games via the Steam Web API and Store API, persists the data to a local SQLite database, and renders two self-contained, offline HTML dashboards:

- `steam_library.html` — filterable/sortable card grid of all games (owned, wishlist, followed)
- `steam_alerts.html` — configurable alert dashboard (price drops, updates, reviews, DLC, news…)

Core features: smart cache (re-fetch only new games), multilingual UI (EN/FR), static HTML output (no server required), multi-threaded fetching, graceful Ctrl+C handling.

## Tech Stack

| Layer          | Technology                                              |
|---------------|----------------------------------------------------------|
| Language       | Python 3.11+                                            |
| HTTP client    | `requests` >= 2.31                                      |
| Data validation| `pydantic` v2 (`BaseModel`, `model_validate`)           |
| Database       | SQLite via stdlib `sqlite3` (WAL mode, FK enforcement)  |
| Build system   | `hatchling` (PEP 517)                                   |
| Standalone exe | `pyinstaller` >= 6.0 (single-file Windows EXE)         |
| Testing        | `pytest` + `pytest-cov` + `responses` (HTTP mocking)   |
| Linting        | `ruff` >= 0.4                                           |
| Type checking  | `mypy` >= 1.10 (strict mode)                            |
| Frontend       | Vanilla HTML/CSS/JS embedded as Python string templates |

## Development Principles

### TDD — Test-Driven Development

- **Always write tests BEFORE implementation code.**
- Workflow: Red → Green → Refactor.
  1. Write a failing test that defines the expected behavior.
  2. Write the minimum code to make the test pass.
  3. Refactor while keeping tests green.
- Every new feature, bugfix, or behavior change MUST start with a test.
- Test files mirror source structure: `steam_tracker/fetcher.py` → `tests/test_fetcher.py`.
- Use fixtures and factories for test data (see `tests/conftest.py`) — avoid hardcoding.
- Mock all HTTP calls with the `responses` library — never make real network requests in tests.

### Code Quality

- **Code language**: All code (variables, functions, classes, comments, docstrings, commit messages) MUST be in **English**.
- **Type hints**: All Python functions must have complete type annotations. `mypy` must pass with zero errors (strict mode).
- **Linting**: `ruff` is the single tool for linting AND formatting Python code. Zero warnings policy.
  - Exception: `E501` (line length) is ignored in `steam_tracker/renderer.py` only — long embedded HTML/CSS/JS is allowed there.
- **`from __future__ import annotations`**: Must be present at the top of every module for deferred annotation evaluation.
- **VS Code integration**: The project is configured so that ruff, mypy, and Pylance report errors/warnings directly in VS Code. Fix all reported issues before considering code complete.
- **Docstrings**: Use Google-style docstrings for all public functions, classes, and modules.
- **No magic numbers**: Use constants (UPPER_SNAKE_CASE). Prices are stored as **integer centimes** (e.g., `1050` = $10.50).

### Documentation

- **Documentation MUST be kept up to date** with every code change.
- **Bilingual**: All documentation files must be written in **both English and French**, in separate files under `docs/en/` and `docs/fr/`.
- Code-level documentation (docstrings, inline comments) is in **English only**.
- Update relevant docs in the SAME commit/PR as the code change.

### Architecture Rules

- **Layered flat architecture** — no sub-packages inside `steam_tracker/` except `sources/` and `i18n/`:
  - `api.py` — I/O boundary: HTTP calls to Steam APIs, returns typed Pydantic models
  - `models.py` — pure domain data objects (Pydantic `BaseModel`)
  - `db.py` — persistence boundary: `Database` class, raw `sqlite3`, `GameRecord` assembly
  - `fetcher.py` — orchestration & concurrency: `SteamFetcher` + `RateLimiter`
  - `renderer.py` — output generation: HTML string templates with embedded CSS/JS
  - `cli.py` — thin entry point: `argparse`, iterates over sources, wires all layers
  - `epic_api.py` — I/O boundary: OAuth2 + library API calls to Epic Games Store
  - `resolver.py` — `AppIdResolver` Protocol + `SteamStoreResolver` + `IGDBResolver` + `resolve_steam_appid()` chain
  - `sources/` — game discovery plugins: `GameSource` Protocol + `get_all_sources()` registry
    - `sources/steam.py` — `SteamSource`: owned library, wishlist, followed games
    - `sources/epic.py` — `EpicSource`: Epic Games Store library via OAuth2
  - `i18n/` — key-based localization: `get_translator(lang)` → callable `Translator`

- **No web framework, no async, no ORM** — purely synchronous Python with stdlib + minimal deps.

- **Database**:
  - `sqlite3` directly (no SQLAlchemy). WAL mode enabled, `PRAGMA foreign_keys = ON`.
  - Prices stored as **integer centimes** (never floats).
  - Schema changes via **additive `ALTER TABLE`** only — columns listed in `_MIGRATIONS`; never drop or recreate tables.
  - `games` table includes `external_id TEXT` for cross-store linking (e.g. `"epic:<catalogItemId>"`).
  - `appid_mappings` table caches external→Steam AppID resolution results; manual mappings are protected from automatic overwrites.

- **i18n**:
  - User-facing strings (CLI output and HTML template markers) all go through `get_translator(lang)`.
  - Add new keys to `steam_tracker/i18n/en.py` (and `fr.py` if translated). Use namespaced prefixes: `cli_*` for CLI, `html_*`/`filter_*`/`lbl_*`/`btn_*`/`badge_*` for HTML.
  - HTML i18n markers use the `__T_key__` convention replaced by `_apply_html_t()` at render time.

- **Concurrency**: `ThreadPoolExecutor` for parallel HTTP fetches. `RateLimiter` uses `threading.Lock`. Each worker gets its own `requests.Session`.

- **HTML output**: Self-contained static files — all CSS and JS are inlined. No CDN calls except Google Fonts. No server required.

### Project Structure

```
steampulse/
├── .github/
│   ├── copilot-instructions.md   # This file
│   └── workflows/
│       ├── ci.yml                # Lint + types + tests (Python 3.11/3.12/3.13)
│       └── build.yml             # PyInstaller EXE + GitHub Release on tag push
├── pyproject.toml
├── steam_tracker/                 # Main Python package
│   ├── __init__.py
│   ├── api.py                    # Steam Web API & Store API wrappers (enrichment only)
│   ├── epic_api.py               # Epic Games OAuth2 + library API wrappers
│   ├── resolver.py               # AppIdResolver Protocol + Steam/IGDB resolvers
│   ├── cli.py                    # CLI entry points (cmd_fetch, cmd_render, cmd_run)
│   ├── db.py                     # SQLite persistence (Database class)
│   ├── fetcher.py                # Multi-threaded fetcher (SteamFetcher + RateLimiter)
│   ├── models.py                 # Pydantic domain models
│   ├── renderer.py               # HTML generation (embedded CSS/JS string templates)
│   ├── sources/
│   │   ├── __init__.py           # GameSource Protocol + get_all_sources() registry
│   │   ├── steam.py              # SteamSource: owned, wishlist, followed
│   │   └── epic.py               # EpicSource: Epic Games Store library
│   └── i18n/
│       ├── __init__.py           # get_translator(), Translator, detect_lang()
│       ├── en.py                 # STRINGS: dict[str, str]
│       └── fr.py                 # STRINGS: dict[str, str]
├── tests/
│   ├── conftest.py               # Shared fixtures (db, sample_game, sample_details, …)
│   ├── test_api.py
│   ├── test_db.py
│   ├── test_epic.py
│   ├── test_fetcher.py
│   ├── test_renderer.py
│   ├── test_resolver.py
│   └── test_sources.py           # GameSource protocol + SteamSource tests
├── build/
│   ├── steampulse.spec           # PyInstaller spec (single-file EXE)
│   ├── entry_steampulse.py       # PyInstaller entry wrapper
│   ├── entry_fetch.py
│   └── entry_render.py
├── docs/
│   ├── en/
│   │   ├── user-guide.md
│   │   └── developer-guide.md
│   └── fr/
│       ├── user-guide.md
│       └── developer-guide.md
├── README.md                     # Bilingual EN + FR
└── CHANGELOG.md                  # Keep a Changelog format, semver
```

### PR preparation workflow

When the user asks to prepare a PR, follow these steps in order:

1. **Tests** — verify existing tests still pass; add or complete tests for all new/changed behavior.
2. **Documentation** — verify and update all relevant docs (user guides EN + FR, README, docstrings).
3. **Roadmap** — update `ROADMAP.md`: move completed features from "Planned" to a new "Done" section with the version label; keep the "Planned" and "Ideas" sections accurate.
4. **Quality checks** — run `ruff check`, `mypy`, and `pytest`; fix all issues before proceeding.
5. **Changelog** — edit `CHANGELOG.md`: move/add entries under `## [Unreleased]`. **Never create a new version section or bump the version number** — that is the user's decision.
6. **Temporary PR description** — create a temporary markdown file in English (e.g. `.github/pull_request_description.md`) to help the user fill in the PR on GitHub. This file must **not** be committed.
7. **Commit** — commit all the above changes (tests, docs, changelog, roadmap) in one clean commit. Do **not** commit the PR description file.

### Commit workflow

When the user asks to commit, follow these steps **in order** before creating the commit:

1. **Tests** — verify existing tests still pass; add or update tests for all new/changed behavior.
2. **Quality checks** — run `ruff check`, `mypy`, and `pytest`; fix all issues before proceeding.
3. **Documentation** — verify and update all relevant docs:
   - `CHANGELOG.md` — add/update entries under `## [Unreleased]`. **Never create a new version section or bump the version number.**
   - `ROADMAP.md` — move completed features from "Planned" to "Done" if applicable; keep "Planned" and "Ideas" accurate.
   - `README.md` — update any affected info (test count, feature list, etc.).
   - `docs/en/` and `docs/fr/` user guides — update if the change affects user-facing behavior.
   - Docstrings — update if public API signatures or behavior changed.
4. **Commit** — stage all modified files (code + tests + docs) and commit in one clean commit with a descriptive message.

### Release workflow

When the user asks to do a release, follow these steps in order:

1. **Ask for the version number** — never choose it yourself. Wait for the user to confirm (e.g. `v1.4.0`).
2. **Bump version** — update `version` in `pyproject.toml` to the new value.
3. **Finalize CHANGELOG** — move everything under `## [Unreleased]` into a new section `## [X.Y.Z] — YYYY-MM-DD` (today's date). Keep the empty `## [Unreleased]` header for future entries.
4. **Update ROADMAP** — ensure the new version appears in the "Done" section with an accurate feature summary; verify "Planned" and "Ideas" sections are still correct.
5. **Update README** — update any version-specific info (test count, badge, etc.) if needed.
6. **Quality checks** — run `ruff check`, `mypy`, and `pytest`; fix all issues before proceeding.
7. **Commit** — one clean commit: `release: vX.Y.Z`.
8. **Tag** — create an annotated git tag `vX.Y.Z`.
9. **Push** — ask the user before pushing the commit and tag to GitHub (this triggers CI: PyInstaller EXE build, GitHub Release, Docker image publish to GHCR).

### Commands

> **Version policy**: Never change the version number in `pyproject.toml` or anywhere else unless explicitly asked by the user.

```bash
# Install (dev)
pip install -e ".[dev]"

# Run (fetch + render in one step)
steampulse --key <API_KEY> --steamid <STEAMID64>

# Separate steps
steam-fetch  --key <API_KEY> --steamid <STEAMID64>
steam-render --steamid <STEAMID64>

# Common flags
steampulse --key K --steamid S --lang fr --workers 8 --news-age 48 --refresh

# Tests
pytest
pytest --cov=steam_tracker

# Lint & format
ruff check steam_tracker
ruff format steam_tracker

# Type checking
mypy steam_tracker

# Build standalone EXE (run from build/ dir)
cd build
pyinstaller steampulse.spec --distpath ../dist --workpath ../build/work --noconfirm
```

### Naming Conventions

| Element              | Convention       | Example                          |
|---------------------|------------------|----------------------------------|
| Python files        | snake_case       | `fetcher.py`, `renderer.py`      |
| Python classes      | PascalCase       | `SteamFetcher`, `RateLimiter`    |
| Python functions    | snake_case       | `get_owned_games()`, `cmd_fetch()`|
| Python constants    | UPPER_SNAKE_CASE | `STEAM_API_BASE`, `_DDL`         |
| Private helpers     | `_` prefix       | `_now()`, `_apply_html_t()`      |
| CLI entry points    | kebab-case       | `steam-fetch`, `steam-render`    |
| DB tables           | snake_case plural| `app_details`, `news`            |
| DB columns          | snake_case       | `appid`, `rtime_last_played`     |
| i18n keys           | snake_case + prefix | `cli_fetching_library`, `badge_earlyaccess` |
| HTML data attributes| data-kebab-case  | `data-playtime`, `data-last-patch-ts` |
| Test files          | `test_` prefix   | `test_api.py`, `test_renderer.py`|
