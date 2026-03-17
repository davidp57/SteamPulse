# SteamPulse — User Guide

🌐 [Version française](../fr/user-guide.md)

## Table of contents

1. [Installation](#1-installation)
2. [Quick start — Setup Wizard](#2-quick-start--setup-wizard)
3. [Config file](#3-config-file)
4. [Steam prerequisites](#4-steam-prerequisites)
5. [Epic Games prerequisites](#5-epic-games-prerequisites)
6. [All-in-one — `steampulse.exe`](#6-all-in-one--steampulseexe)
7. [All options](#7-all-options)
8. [Navigating the interface](#8-navigating-the-interface)
9. [Cache strategy & refresh](#9-cache-strategy--refresh)
10. [Advanced usage — separate steps](#10-advanced-usage--separate-steps)
11. [FAQ](#11-faq)
12. [Docker deployment](#12-docker-deployment)

---

## 1. Installation

### Option A — Standalone executable (recommended, Windows only)

Download `steampulse.exe` from the [latest GitHub release](https://github.com/davidp57/SteamPulse/releases/latest).  
No Python required. Place the file wherever you like and run it from a terminal.

### Option B — From source (Python 3.11+)

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # Linux / macOS
pip install -e .
```

In this case, replace `steampulse.exe` with `steampulse` in all examples below.

---

## 2. Quick start — Setup Wizard

The easiest way to get started is the interactive setup wizard. It guides you step by step through all credentials and settings, then writes a config file so you never have to pass flags on the command line again.

### Run the wizard

```
steam-setup
```

Or, if you're using the standalone executable, just run it without any flags the first time — the wizard starts automatically when no credentials are found:

```
steampulse.exe
```

You can also force the wizard at any time with `--setup`:

```
steampulse.exe --setup
```

### What the wizard covers

1. **Steam** — API key and SteamID64
2. **Epic Games** (optional) — full OAuth2 flow: the wizard displays the auth URL, optionally opens your browser, prompts you to copy the `authorizationCode` from the resulting JSON page, and automatically exchanges it for a persistent refresh token. No programmatic JSON parsing required — just one copy-paste from your browser.
3. **Twitch/IGDB** (optional) — client ID and secret for better Epic→Steam AppID resolution
4. **Settings** (optional) — database path, worker threads, news age, language

At the end, the wizard shows a summary and asks for confirmation before writing the file.

### Config file location

| Platform | Path |
|---|---|
| Windows | `%APPDATA%\steampulse\config.toml` |
| Linux / macOS | `$XDG_CONFIG_HOME/steampulse/config.toml` (default: `~/.config/steampulse/config.toml`) |

A message is printed whenever the config is loaded or written:
```
  ✔ Config loaded from C:\Users\you\AppData\Roaming\steampulse\config.toml
```

---

## 3. Config file

SteamPulse automatically loads `config.toml` on every run. CLI flags always take precedence over config values, and new credentials passed on the command line are saved back to the config automatically.

### File format

```toml
[steam]
key      = "YOUR_STEAM_API_KEY"
steamid  = "76561198000000000"

[epic]
refresh_token = "..."
account_id    = "..."

[twitch]
client_id     = "..."
client_secret = "..."

[settings]
db        = "steam_library.db"
workers   = 4
news_age  = 24
lang      = "en"
```

All sections and keys are optional — any not present fall back to CLI defaults.

### Custom config path

You can point to a different config file with `--config`:

```
steampulse.exe --config /path/to/myconfig.toml
```

---

## 4. Steam prerequisites

### Steam API key

1. Log in at <https://steamcommunity.com/dev/apikey>
2. Enter any domain name (e.g. `localhost`)
3. Copy the displayed key (32 hexadecimal characters)

> ⚠️ The key grants read access to your account. Do not share it or commit it to a repository.

### Your SteamID64

Go to <https://steamid.io> and enter your Steam username or profile URL.  
The SteamID64 is a 17-digit number starting with `765`.

---

## 5. Epic Games prerequisites

Epic integration is **optional**. Skip this section if you only use Steam.

SteamPulse can import your Epic Games library and attempt to resolve each game to a Steam AppID (to fetch store details and news). Games that cannot be resolved still appear in the dashboard, tagged as Epic, without Steam enrichment.

### Authentication — first run (authorization code)

1. Open a browser and go to:  
   `https://www.epicgames.com/id/login?redirectUrl=https%3A%2F%2Fwww.epicgames.com%2Fid%2Fapi%2Fredirect%3FclientId%3D34a02cf8f4414e29b15921876da36f9a%26responseType%3Dcode`
2. Log in with your Epic account.
3. You will be redirected to a JSON page — copy the value of `authorizationCode`.
4. Pass it with `--epic-auth-code <CODE>`. This is a **one-time** code.

### Authentication — subsequent runs (refresh token)

After the first login, the wizard (or the `--epic-auth-code` flow) automatically saves a **refresh token** to the config file. On subsequent runs, SteamPulse reuses it transparently. The token is valid for 30 days and is renewed automatically on each use, so it effectively never expires with regular use.

You can also pass it explicitly on the command line:

```
steampulse.exe --key <API_KEY> --steamid <STEAMID64> \
  --epic-refresh-token <TOKEN> \
  --epic-account-id <ACCOUNT_ID>
```

### Optional — IGDB resolver

For better Steam AppID resolution accuracy, provide Twitch API credentials (used to query IGDB):

1. Create an app at <https://dev.twitch.tv/console/apps>
2. Pass `--twitch-client-id` and `--twitch-client-secret`

Without IGDB, SteamPulse falls back to fuzzy matching against the Steam Store search API.

---

## 6. All-in-one — `steampulse.exe`

```
steampulse.exe --key <API_KEY> --steamid <STEAMID64>
```

This single command:
1. Fetches your library, wishlist, and news for each game via the Steam API
2. Saves everything to a local SQLite database
3. Generates the HTML pages directly

When done, open `steam_library.html` in a browser — **no server required**.

### What gets fetched

For each Steam game (owned, wishlist, or followed):
- **App details**: name, type, description, developers, publishers, genres, categories, platforms, price, Metacritic score, achievement count, release date
- **News**: the 5 most recent official news items (title, date, URL, author, tags)

For each **Epic** game: the game is resolved to a Steam AppID when possible — if found, the same enrichment applies. Unresolved games appear in the dashboard without store details or news.

### Sample output

```
📦 Fetching Steam library...
   ✅ 2190 owned game(s)
🎁 Fetching wishlist...
   ✅ 54 wishlist game(s) · 54 new
   12 game(s) to fetch · 387 news to refresh (1845 already up to date)
[  1/399] Elden Ring
[  2/399] Cyberpunk 2077
...
✅ Fetch done — 399 entry/entries updated in steam_library.db
🖥  Generating HTML pages...
✅ 2244 games · library → C:\...\steam_library.html
   11220 news → C:\...\steam_news.html
```

---

## 7. All options

| Option | Default | Description |
|---|---|---|
| `--key` | *(config or required)* | Steam Web API key |
| `--steamid` | *(config or required)* | Profile SteamID64 |
| `--db` | `steam_library.db` | Path to the SQLite database |
| `--output` | `steam_library.html` | Library page output path |
| `--workers` | `4` | Number of parallel fetch threads |
| `--max N` | *(none)* | Limit fetch to N games (testing) |
| `--refresh` | off | Ignore cache, re-fetch everything |
| `--news-age HOURS` | `24` | Re-fetch news for games whose cached news is older than N hours |
| `--no-wishlist` | off | Skip wishlist fetch |
| `--followed` | off | Fetch followed games (opt-in, see note) |
| `--lang` | *(system)* | Force interface language (`en`, `fr`, …). Defaults to the system locale, falls back to `en`. |
| `--config` | *(platform default)* | Path to a custom config TOML file |
| `--setup` | off | Run the interactive setup wizard and exit |
| `-v` / `--verbose` | off | Enable DEBUG logging |

**Epic Games options:**

| Option | Default | Description |
|---|---|---|
| `--epic-auth-code` | *(none)* | One-time Epic authorization code (first login) |
| `--epic-refresh-token` | *(none)* | Epic refresh token (persistent auth, saved automatically after first login) |
| `--epic-account-id` | *(none)* | Epic account ID (required alongside `--epic-refresh-token`) |
| `--twitch-client-id` | *(none)* | Twitch/IGDB client ID (better AppID resolution) |
| `--twitch-client-secret` | *(none)* | Twitch/IGDB client secret |

> **Note on `--followed`**: the Steam Web API no longer returns followed games with a standard key. This flag is available but will generally return an empty list.

---

## 8. Navigating the interface

### Library page (`steam_library.html`)

**Toolbar — main row (always visible):**
- **Search** — filters games by name in real time (`/` or `Ctrl+K`)
- **Sort** — by name, Metacritic score, playtime, release date, last update, last news date
- **⚙ Filters** — expands/collapses the filter panel; a badge shows the number of active filters
- **Reset** — clears all filters and search (only appears when something is active)
- **☰ Liste / ⊞ Grille** — toggle between card grid and table list view
- **🗞 News** — opens the news feed page (carries compatible filters via URL hash)

**Filter panel (collapsible):**

| Group | Options | Behaviour |
|---|---|---|
| **Status** | All · Early Access · Released · Upcoming | Single-select |
| **Store** | 🎮 Steam · ⚡ Epic | Multi-select (OR) — both active by default; last active store cannot be deactivated |
| **Collection** | All · Owned · 🎁 Wishlist · 👁 Followed | Single-select |
| **News type** | All types · 📋 Patch notes · 📰 News | Single-select |
| **Playtime** | All · Never played · < 1 h · 1–10 h · > 10 h | Single-select |
| **Metacritic** | All · No score · < 50 · 50–75 · > 75 | Single-select |
| **Recent update** | All · 2 days · 5 days · 15 days · 30 days (based on last patch note date) | Single-select |

> The **Store** and **Collection** filters are combined with AND: only games matching an active store **and** the selected collection status are shown.

All filter and sort state is persisted in the URL hash so you can bookmark or share a filtered view.

**Cards:**

Each card shows:
- Game header image
- Name + status badge (Early Access · Released 1.0 · Upcoming)
- Metacritic score with colour coding (green ≥ 75 · orange ≥ 50 · red < 50)
- Platform icons (Windows / Mac / Linux)
- Genres
- 📅 Release date · 📰 Latest news date · 🕹 Playtime _(or 🎁 Wishlist / 👁 Followed / 🎮 Epic)_
- `#appid` — click to open the Steam store page (or hover the card to see the store hint)

Clicking anywhere on a card opens the Steam store page in a new tab.

### News page (`steam_news.html`)

- All news from all games, sorted by descending date
- Same two-layer toolbar: search in the main row, Status, Store, Collection and Type news filters in the collapsible panel
- Type badge on each row (green for `patchnotes`, grey for others)
- Live result counter
- Click a row to open the news item on Steam

---

## 9. Cache strategy & refresh

| Scenario | Behaviour |
|---|---|
| New game (never seen) | App details + news fetched |
| Cached game, news < `--news-age` hours old | Skipped entirely |
| Cached game, news ≥ `--news-age` hours old | News re-fetched, app details preserved |
| `--refresh` flag set | Everything re-fetched, cache ignored |

**Tip:** run `steampulse.exe` daily without extra flags to keep news up to date. Use `--refresh` only when game metadata has changed (price update, leaving Early Access, etc.).

---

## 10. Advanced usage — separate steps

If you installed SteamPulse from source, two separate commands are also available to run fetch and render independently:

### `steam-fetch` — fetch only

```
steam-fetch --key <API_KEY> --steamid <STEAMID64>
```

Same options as `steampulse.exe`, except `--output`. Epic options (`--epic-auth-code`, etc.) are also accepted. Saves data to the SQLite database without generating HTML.

### `steam-render` — render only

```
steam-render --steamid <STEAMID64>
```

| Option | Default | Description |
|---|---|---|
| `--db` | `steam_library.db` | Source SQLite database |
| `--steamid` | *(required)* | SteamID64 (shown in page header) |
| `--output` | `steam_library.html` | Library page output path |
| `--lang` | *(system)* | Force interface language (`en`, `fr`, …) |

Reads the SQLite database and regenerates the HTML from existing data. Useful for re-rendering after a SteamPulse update without re-fetching.

---

## 11. FAQ

**I have games on Epic that don't appear with store details — why?**  
SteamPulse tries to match each Epic game to a Steam AppID using fuzzy name matching (and IGDB if you provide Twitch credentials). If no match is found, the game still appears in the dashboard with the 🎮 Epic badge, but without Steam details or news.

**My Steam profile is private — will it still work?**  
The API key bypasses privacy restrictions for requests about your own account.

---

## 12. Docker deployment

The Docker image bundles **nginx** (serves the generated HTML pages) and a **scheduler** (runs SteamPulse at a configurable interval) in a single self-contained container.  
No Python or extra tooling is required on the host — only Docker.

> **Synology NAS**: upload the files via File Station and use the Container Manager UI, or SSH into the NAS and follow the CLI steps below.

### Two ways to configure credentials

#### Option A — Environment variables (simple, Steam-only)

Set `STEAM_API_KEY` and `STEAM_ID` in `.env`. The container generates a `config.toml` from them at startup.

```env
STEAM_API_KEY=your_32_char_api_key
STEAM_ID=76561198000000000
```

This is the quickest path for a Steam-only setup.

#### Option B — Mounted config file (recommended for Epic / Twitch)

Run the interactive setup wizard **once on a machine where SteamPulse is installed** (not inside the container):

```bash
steam-setup
```

The wizard handles Steam, Epic OAuth2 (including the browser flow), and Twitch, then writes a `config.toml` whose path is shown at the end.  
Copy that file next to `docker-compose.yml`:

```bash
cp ~/.config/steampulse/config.toml ./config.toml   # Linux/macOS
# or
copy %APPDATA%\steampulse\config.toml .\config.toml  # Windows
```

Then uncomment the config volume line in `docker-compose.yml`:

```yaml
volumes:
  - steampulse_data:/data
  - ./config.toml:/config/config.toml:ro   # ← uncomment this
```

When a config file is mounted, the credential env vars (`STEAM_API_KEY`, `STEAM_ID`, `EPIC_*`, `TWITCH_*`) are ignored. Scheduling variables (`INTERVAL_HOURS`, `REFRESH`) are always read from the environment.

#### Why not run the wizard inside the container?

The wizard requires an interactive terminal and a browser for Epic OAuth2 — neither of which is available in an unattended container. Option B (wizard once locally, then mount the config file) is the clean solution.

### Getting started

1. **Get the Docker files:**
   ```bash
   git clone https://github.com/davidp57/SteamPulse.git && cd SteamPulse
   ```
2. **Prepare credentials** using Option A or B above.
3. **Build and start:**
   ```bash
   docker compose up -d
   ```

Open **http://\<host\>:8080** — a loading page is shown while the first fetch runs (15–30 min for a large library).

| Variable | Default | Description |
|---|---|---|
| `STEAM_API_KEY` | *(required, option A)* | Steam Web API key |
| `STEAM_ID` | *(required, option A)* | SteamID64 |
| `INTERVAL_HOURS` | `4` | Hours between automatic re-fetches |
| `HOST_PORT` | `8080` | Host port mapped to the nginx port 80 |
| `SP_LANG` | *(from config)* | Interface language (`en` or `fr`), option A only |
| `WORKERS` | `4` | Parallel fetch threads, option A only |
| `NEWS_AGE` | `24` | Re-fetch news older than N hours, option A only |
| `REFRESH` | `false` | Set to `true` to ignore cache on every run |
| `EPIC_REFRESH_TOKEN` | *(none)* | Epic refresh token, option A only |
| `EPIC_ACCOUNT_ID` | *(none)* | Epic account ID, option A only |
| `TWITCH_CLIENT_ID` | *(none)* | Twitch/IGDB client ID, option A only |
| `TWITCH_CLIENT_SECRET` | *(none)* | Twitch/IGDB client secret, option A only |

> `INTERVAL_HOURS` and `REFRESH` are always read from the environment, even when a config file is mounted.

### Epic Games in Docker

Epic requires an OAuth2 browser flow that cannot run in an unattended container.

- **Option A**: run `steam-setup` locally once; copy `EPIC_REFRESH_TOKEN` and `EPIC_ACCOUNT_ID` from the generated `config.toml` into `.env`.
- **Option B** (recommended): mount the full `config.toml` — it already contains all Epic credentials. No need for individual env vars.

### Data volume

All persistent data (SQLite database + generated HTML pages) is stored in the named Docker volume `steampulse_data` mounted at `/data` inside the container.  
The files are accessible from the host via:

```bash
docker volume inspect steampulse_data
```

### Useful commands

```bash
# Start in background
docker compose up -d

# Follow logs (scheduler output)
docker compose logs -f

# Force an immediate re-fetch (outside the schedule)
docker compose exec steampulse bash -c \
  'steampulse --config /run/steampulse/config.toml --db /data/steam_library.db --output /data/steam_library.html --refresh'

# Stop container (data volume is preserved)
docker compose down

# Remove everything including the volume
docker compose down -v
```

### Pre-built image (GHCR)

If you prefer not to build locally, you can pull the image published to the GitHub Container Registry:

```yaml
# In docker-compose.yml, replace the build: block with:
image: ghcr.io/davidp57/steampulse:latest
```

New images are published automatically on each new release tag.

**Is any data sent anywhere?**  
No. Everything stays local: the SQLite database on your disk, HTML pages generated locally. Only read requests are made to the public Steam API.

**How long does the first fetch take?**  
With 2000 games and 4 workers, expect ~15–20 minutes (rate limit ~200 req/5 min on the Store API).

**Can I re-run `steampulse.exe` without re-fetching everything?**  
Yes. The smart cache avoids re-fetching already up-to-date games. Only new games and those with stale news are refreshed.

**How do I interrupt a fetch in progress?**  
Press `Ctrl+C` — in-flight tasks are cancelled cleanly and already-collected data is saved.
