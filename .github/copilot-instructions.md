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

## Git Flow

This project follows **Git Flow**:
- `main` — tagged production releases only
- `develop` — integration branch, always deployable
- `feature/*` — new features branched from `develop`
- `fix/*` — bug fixes branched from `develop`
- `hotfix/*` — urgent fixes branched from `main`
- `release/*` — release preparation branched from `develop`

**Rules:**
- Never commit directly to `main` or `develop`.
- All work happens on `feature/*` or `fix/*` branches, opened as PRs into `develop`.
- When preparing a release (version bump, CHANGELOG freeze, release notes), always work on a dedicated `release/x.y.z` branch. If the current branch is not `release/*`, create it first.

**Multi-machine workflow:** always run `git pull --rebase` before starting work on a branch to avoid non-fast-forward push conflicts.

## Conventional Commits

All commit messages follow the **Conventional Commits** format (`type(scope): description` in English):

```
feat(cli): add --refresh flag to force re-fetch all games
fix(db): correct migration guard for appid_mappings table
docs(user-guide): document GOG OAuth2 setup steps
test(resolver): add unit tests for edition-suffix stripping
refactor(fetcher): extract rate-limiter to separate module
chore(deps): upgrade requests to 2.32
ci(workflows): add Python 3.13 to test matrix
```

Types: `feat` · `fix` · `docs` · `test` · `refactor` · `chore` · `ci`

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
│   ├── fr/
│   │   ├── user-guide.md
│   │   └── developer-guide.md
│   └── releases/
│       └── vX.Y.Z.md             # Per-release notes (EN)
├── README.md                     # Bilingual EN + FR
├── CHANGELOG.md                  # Keep a Changelog format, semver
└── BACKLOG.md                    # Project backlog — single source of truth
```

### Commit, push and PR workflow

When the user asks to commit, push and/or open a PR, follow these steps **in order**:

1. **Run the full quality gate** — all checks must be green (see **Quality gate** section below)
2. **Verify zero errors in VS Code**
3. **Apply the per-change checklist** — CHANGELOG, BACKLOG.md, patch bump (see **Per-change checklist** section below)
4. **Commit** using Conventional Commits format
5. **Push** the branch
6. **Open a PR on GitHub** targeting the correct base branch (follow Git Flow):
   - `feature/*` / `fix/*` → PR into `develop`
   - `release/*` → PR into `main`
   - Provide the PR title and description as copyable markdown blocks in the chat
   - Request a **Copilot review** on the PR
   - When preparing the PR description: create a temporary file `.github/pull_request_description.md` for the user's convenience; this file must **not** be committed (it is listed in `.gitignore`)
7. **Monitor reviews** — check for review comments every ~2 minutes until the review is complete:
   - Address every comment: fix the code, re-run the quality gate
   - Resolve the review thread once the fix is applied
   - Push the updated commits
   - Repeat until all threads are resolved and the PR is approved

### Release workflow

When the user asks to do a release, follow these steps **in order**:

1. **Ensure branch is `release/x.y.z`** — if the current branch is not `release/*`, create or switch to it before continuing.
2. **Ask for the version number** — never choose it yourself. Wait for the user to confirm (e.g. `v2.2.0`).
3. **Bump version** — update `version` in `pyproject.toml` to the new value.
4. **Finalize CHANGELOG** — move everything under `## [Unreleased]` into a new section `## [X.Y.Z] — YYYY-MM-DD` (today's date). Keep the empty `## [Unreleased]` header for future entries.
5. **Update BACKLOG.md** — ensure completed lots are marked with today's completion date.
6. **Update ROADMAP.md** — ensure the new version appears with an accurate feature summary; verify Planned and Ideas sections are still correct.
7. **Update README** — update test count and any version-specific info.
8. **Create release notes** — `docs/releases/vX.Y.Z.md` (English only) with a short summary, new features, and fixes.
9. **Quality gate** — run the full gate; fix all issues before proceeding.
10. **Commit** — `chore(release): bump version to X.Y.Z`
11. **Tag** — create an annotated git tag `vX.Y.Z`.
12. **Ask before pushing** — wait for user confirmation before pushing the commit and tag to GitHub (triggers CI: PyInstaller EXE build, GitHub Release, Docker image publish to GHCR).

### Release collection checklist

Before finalising release documentation, verify all points below:

1. `git log <last_tag>..HEAD --oneline` reviewed, grouped by ticket type (BIZ/TEC/CHR).
2. Every major feature appears in `CHANGELOG.md` under the correct section.
3. `docs/en/` and `docs/fr/` user guides updated for new or changed user-facing workflows.
4. `BACKLOG.md` lot statuses aligned with delivered tickets.
5. `ROADMAP.md` version entry accurate (functional lots detailed, technical lots one-liner).
6. `docs/releases/vX.Y.Z.md` exists and matches CHANGELOG scope.
7. `README.md` updated (test count, feature list if applicable).
8. Final consistency pass: no significant feature present in code/commits but absent from release docs.

### Quality gate

Run the following checks **before every push**. All must be green. Never bypass with `--no-verify`.

```bash
ruff check steam_tracker/ tests/
ruff format --check steam_tracker/ tests/   # fix with: ruff format steam_tracker/ tests/
mypy steam_tracker/
pytest --tb=short -q
```

### Per-change checklist

After every change (feature, fix, refactor):

1. Add or update tests (TDD: write the test first)
2. Run the full quality gate — all green
3. Verify zero errors in VS Code
4. Update `CHANGELOG.md` under `## [Unreleased]`. **Never create a new version section or bump the version number.**
5. Update `BACKLOG.md` — advance or close the relevant ticket

### Backlog management

`BACKLOG.md` (repo root) is the single source of truth for all tracked work items.

- **Ticket types**: `BIZ-NNN` (user-visible feature), `TEC-NNN` (technical/refactor), `CHR-NNN` (chore/maintenance)
- **Priorities**: P1 (critical / blocks users), P2 (important), P3 (nice to have)
- **Lots**: group related tickets into named lots with a target version; each lot maps to a `feature/*` branch and a PR
- **Hors lots**: items not yet assigned to a lot live in the "Hors lots" table
- When a ticket is completed, move it to the "Lots terminés" section with a completion date
- Update `BACKLOG.md` immediately when identifying, starting, or completing any ticket
- **Estimation formula**: estimate raw implementation time × 1.15 (15 % margin), rounded to nearest 5 min; per-lot total = sum of ticket estimates + 15 min project management

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
