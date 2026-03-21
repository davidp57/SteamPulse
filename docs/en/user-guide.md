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
2. **Epic Games** (optional) — full OAuth2 flow: the wizard displays the auth URL, optionally opens your browser, prompts for the authorization code, and automatically exchanges it for a persistent refresh token. No manual JSON navigation required.
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
   42 alerts → C:\...\steam_alerts.html
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
- **🔔 Alerts** — opens the alerts dashboard; carries over compatible filters (store, collection) via URL hash

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

> Hover any filter button to see a tooltip explaining what it filters.

> The **Store** and **Collection** filters are combined with AND: only games matching an active store **and** the selected collection status are shown.

> On mobile (narrow screens), the filter panel opens as a full-screen overlay with a close button at the top.

All filter and sort state is persisted in the URL hash so you can bookmark or share a filtered view.

**Cards:**

Each card shows:
- Game header image (native 460×215 aspect ratio — never stretched or squashed; may be cropped if the source image differs from this ratio)
- Name + status badge (Early Access · Released 1.0 · Upcoming)
- Metacritic score with colour coding (green ≥ 75 · orange ≥ 50 · red < 50) — hover to see the score/100 and quality label tooltip
- Platform icons (Windows / Mac / Linux)
- Developer · Genres
- 📅 Release date · 📰 Latest news date · 🕹 Playtime _(or 🎁 Wishlist / 👁 Followed / 🎮 Epic)_

Clicking anywhere on a card opens the Steam store page in a new tab.

If a game has news, a **▼ N updates** bar appears at the bottom of the card. Clicking it expands the news list as a floating overlay on top of the cards below — the rest of the grid dims and blurs to focus attention. Only one card can be expanded at a time; click outside to close.

### Alerts page (`steam_alerts.html`)

**Toolbar — main row (always visible):**
- **Search** — filters alerts by game name in real time
- **Sort** — by date (newest/oldest), name (A–Z / Z–A), playtime, Metacritic score
- **View mode** — three togglable views:
  - **Combined** — all alert cards in a single flat list
  - **By rule** — cards grouped under collapsible section headers (one per alert rule)
  - **By game** — cards grouped by game name
- **Group controls** (visible only in grouped views):
  - **Group search** — filters section headers by name in real time
  - **Expand all / Collapse all** — toggle button to open or close every group at once
- **⚙ Filters** — expands/collapses the filter panel; a badge shows the number of active filters
- **Reset** — clears all filters, search and sort to defaults
- **Mark all as read** — marks every visible alert as read

**Filter panel (collapsible):**

| Group | Options | Behaviour |
|---|---|---|
| **Status** | All · Early Access · Released · Upcoming | Single-select |
| **Store** | 🎮 Steam · ⚡ Epic | Multi-select (OR) — both active by default |
| **Collection** | All · Owned · 🎁 Wishlist · 👁 Followed | Single-select |
| **News type** | All types · 📋 Patch notes · 📰 News | Single-select |
| **Playtime** | All · Never played · < 1 h · 1–10 h · > 10 h | Single-select |
| **Metacritic** | All · No score · < 50 · 50–75 · > 75 | Single-select |
| **Recent update** | All · 2 days · 5 days · 15 days · 30 days | Single-select |

> The filter panel is shared between the library and alerts pages. **Store** and **Collection** filters selected on one page are carried over when navigating to the other.

**Accordion sections (grouped views):**

In "By rule" and "By game" views, alerts are grouped under collapsible sections:
- Click a section header (or its chevron ❯) to expand or collapse it
- All sections start collapsed by default
- Use the **Expand all / Collapse all** button to toggle every section at once
- The **group search** field filters sections by header name — non-matching sections are hidden

**Alert cards:**

Each card shows:
- Rule icon + rule name
- Game header image
- Game name (clickable → opens the Steam store page)
- Alert date + read/unread status (click to toggle)
- News snippet (title + source) for news-based alerts
- Build ID badge when relevant (e.g. `build 12345` for silent update detection)

**Read/unread tracking:**
- State is stored locally in `localStorage` — no server needed
- Click an individual card to toggle read/unread
- Use "Mark all as read" to mark everything at once

Alert rules are configured in `config.toml` under `[[alerts]]` sections. Run `steam-setup` to see and edit the default rules.

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

**Is any data sent anywhere?**  
No. Everything stays local: the SQLite database on your disk, HTML pages generated locally. Only read requests are made to the public Steam API.

**How long does the first fetch take?**  
With 2000 games and 4 workers, expect ~15–20 minutes (rate limit ~200 req/5 min on the Store API).

**Can I re-run `steampulse.exe` without re-fetching everything?**  
Yes. The smart cache avoids re-fetching already up-to-date games. Only new games and those with stale news are refreshed.

**How do I interrupt a fetch in progress?**  
Press `Ctrl+C` — in-flight tasks are cancelled cleanly and already-collected data is saved.

---

## 12. Docker deployment

> **TL;DR** — Copy your `config.toml`, download `docker-compose.yml` from the
> release page, place them in the same folder, run `docker compose up -d`, open
> `http://<host>:8080`.

SteamPulse publishes a ready-to-use Docker image on every release:

```
ghcr.io/davidp57/steampulse:latest
```

The container fetches your game data on a schedule and serves the dashboards on
port 80 via nginx. No build required — pull and run.

---

### Step 1 — Get your `config.toml`

The `config.toml` file is the only thing the container needs. It holds all
your credentials (Steam API key, SteamID, Epic tokens, Twitch credentials…).

**Already using `steampulse.exe` on Windows?**
The wizard created it on first launch. Find it at:

```
%APPDATA%\steampulse\config.toml
```

Copy it to the folder where you will run Docker (e.g. your NAS, a server, or your
local machine). That is all — go to Step 2.

**Never ran `steampulse.exe` yet?**
Launch it once — the wizard starts automatically, saves the file, and exits.
Your `config.toml` is then ready.

> **Epic Games / Twitch:** the OAuth2 login flow requires a real browser and
> cannot run inside a container. You must complete the wizard on a local machine
> at least once. After that, the refresh token stored in `config.toml` handles
> re-authentication automatically — no further interaction needed.

---

### Step 2 — Download `docker-compose.yml` and start the container

The `docker-compose.yml` for SteamPulse is included in each GitHub release.
Download the file for your version:

```
https://github.com/davidp57/SteamPulse/releases/latest/download/docker-compose.yml
```

Place it in the same folder as your `config.toml`:

```
your-folder/
├── docker-compose.yml   ← downloaded from the release
├── config.toml          ← copied from %APPDATA%\steampulse\
└── data/                ← created automatically by Docker
    ├── steam_library.db
    ├── steam_library.html
    └── steam_alerts.html
```

Create the data folder then start the container:

```bash
mkdir data
docker compose up -d
```

Docker pulls the image automatically on first run.

---

### Step 3 — Open your dashboards

Navigate to `http://localhost:8080` (or `http://<server-ip>:8080` from another
device).

The container regenerates the dashboards every `INTERVAL_HOURS` hours. Your
SQLite database and HTML pages are in the `./data/` folder next to
`docker-compose.yml` — directly accessible from the NAS. This folder
survives container restarts and image updates.

---

### Managing your container

```bash
# View logs
docker compose logs -f

# Force an immediate re-fetch right now (outside the schedule)
docker compose exec steampulse steampulse \
  --config /run/steampulse/config.toml \
  --db /data/steam_library.db \
  --output /data/steam_library.html \
  --refresh

# Update to the latest image
docker compose pull && docker compose up -d

# Wipe all data and start from scratch  ⚠ deletes the database
rm -rf ./data && docker compose up -d
```

---

### Deploying on a NAS (Synology, QNAP…)

The steps are the same as above — the NAS just acts as your Docker host.

**Synology — Container Manager (DSM 7.2+):**

1. Use **File Station** to create a folder (e.g. `/volume1/docker/steampulse`)
2. Upload `docker-compose.yml` and `config.toml` to that folder
3. In that folder, create a `data` subfolder (via File Station)
4. Open **Container Manager** → **Projects** → **Create**
5. Select the folder you just created — it detects `docker-compose.yml` automatically
6. Click **Build** — the image is pulled from GHCR, no local build needed
7. Open `http://<NAS-IP>:8080`

**Portainer:**

> **Known limitation:** when you paste a Compose file into Portainer's stack editor,
> relative paths like `./config.toml` are resolved against Portainer's internal
> working directory (e.g. `/data/compose/3/`), **not** your folder. This causes
> a `Bind mount failed` error.

The recommended approach is **not** to use Portainer's paste editor for SteamPulse.
Instead, SSH into the Docker host, place the files there, and run Compose directly:

```bash
mkdir -p /opt/steampulse/data
# copy config.toml to /opt/steampulse/config.toml via scp or File Station
cd /opt/steampulse
curl -LO https://github.com/davidp57/SteamPulse/releases/latest/download/docker-compose.yml
docker compose up -d
```

If you still want to deploy via Portainer's UI, use **absolute paths** in the
compose file. Edit the `volumes:` section before pasting:

```yaml
volumes:
  - /opt/steampulse/data:/data
  - /opt/steampulse/config.toml:/config/config.toml:ro
```

Make sure `/opt/steampulse/config.toml` exists on the host **before** clicking
**Deploy the stack**, otherwise the bind mount will fail.

The container restarts automatically after a reboot thanks to
`restart: unless-stopped`.

---

### Updating the image

A new image is published on every release. Your data in `./data/` is never
touched by an update.

**Image tags:**

| Tag | Source | Use |
|---|---|---|
| `latest` | `main` branch / releases | **Production — use this** |
| `develop` | `develop` branch | Pre-release testing only |
| `v1.2.3` | Version tag | Pin to a specific release |

**Terminal / SSH (any host):**

```bash
cd /path/to/your-folder
docker compose pull
docker compose up -d
```

**Synology — Container Manager:**

1. Open **Container Manager** → **Projects**
2. Select the `steampulse` project
3. Click **Action** → **Build** — Container Manager pulls the new image and
   recreates the container automatically

> **Note:** some DSM versions only restart the container without re-pulling.
> If the steps below show an old date, open a SSH session on the NAS and run
> `docker compose pull && docker compose up -d` from the project folder.

**Portainer:**

1. Go to **Stacks** → select `steampulse`
2. Click **Editor**
3. Click **Update the stack**
4. Check **Re-pull image and redeploy**

**Verify that the new image is actually running:**

```bash
# Date the local image was built (compare with the release date)
docker image inspect ghcr.io/davidp57/steampulse:latest --format='{{.Created}}'

# List local images with their creation date
docker images ghcr.io/davidp57/steampulse
```

If the date shown is older than the release, the old image is still cached.
Run `docker compose pull && docker compose up -d` to force the update.

**Testing the `develop` build before a release:**

The `develop` tag is not aliased to `latest` — it is a separate image. To
test it on your NAS, pull and retag it locally:

```bash
docker pull ghcr.io/davidp57/steampulse:develop
docker tag ghcr.io/davidp57/steampulse:develop ghcr.io/davidp57/steampulse:latest
docker compose up -d
```

Revert to the official image at any time with `docker compose pull && docker compose up -d`.
