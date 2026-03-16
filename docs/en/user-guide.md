# SteamPulse — User Guide

🌐 [Version française](../fr/user-guide.md)

## Table of contents

1. [Installation](#1-installation)
2. [Steam prerequisites](#2-steam-prerequisites)
3. [Epic Games prerequisites](#3-epic-games-prerequisites)
4. [All-in-one — `steampulse.exe`](#4-all-in-one--steampulseexe)
5. [All options](#5-all-options)
6. [Navigating the interface](#6-navigating-the-interface)
7. [Cache strategy & refresh](#7-cache-strategy--refresh)
8. [Advanced usage — separate steps](#8-advanced-usage--separate-steps)
9. [FAQ](#9-faq)

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

## 2. Steam prerequisites

### Steam API key

1. Log in at <https://steamcommunity.com/dev/apikey>
2. Enter any domain name (e.g. `localhost`)
3. Copy the displayed key (32 hexadecimal characters)

> ⚠️ The key grants read access to your account. Do not share it or commit it to a repository.

### Your SteamID64

Go to <https://steamid.io> and enter your Steam username or profile URL.  
The SteamID64 is a 17-digit number starting with `765`.

---

## 3. Epic Games prerequisites

Epic integration is **optional**. Skip this section if you only use Steam.

SteamPulse can import your Epic Games library and attempt to resolve each game to a Steam AppID (to fetch store details and news). Games that cannot be resolved still appear in the dashboard, tagged as Epic, without Steam enrichment.

### Authentication — first run (authorization code)

1. Open a browser and go to:  
   `https://www.epicgames.com/id/login?redirectUrl=https%3A%2F%2Fwww.epicgames.com%2Fid%2Fapi%2Fredirect%3FclientId%3D34a02cf8f4414e29b15921876da36f9%26responseType%3Dcode`
2. Log in with your Epic account.
3. You will be redirected to a JSON page — copy the value of `authorizationCode`.
4. Pass it with `--epic-auth-code <CODE>`. This is a **one-time** code.

### Authentication — subsequent runs (device credentials)

For headless or automated runs, use device credentials (obtained on first auth by the Epic API):

```
steampulse.exe --key <API_KEY> --steamid <STEAMID64> \
  --epic-device-id <DEVICE_ID> \
  --epic-account-id <ACCOUNT_ID> \
  --epic-device-secret <SECRET>
```

### Optional — IGDB resolver

For better Steam AppID resolution accuracy, provide Twitch API credentials (used to query IGDB):

1. Create an app at <https://dev.twitch.tv/console/apps>
2. Pass `--twitch-client-id` and `--twitch-client-secret`

Without IGDB, SteamPulse falls back to fuzzy matching against the Steam Store search API.

---

## 4. All-in-one — `steampulse.exe`

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

## 5. All options

| Option | Default | Description |
|---|---|---|
| `--key` | *(required)* | Steam Web API key |
| `--steamid` | *(required)* | Profile SteamID64 |
| `--db` | `steam_library.db` | Path to the SQLite database |
| `--output` | `steam_library.html` | Library page output path |
| `--workers` | `4` | Number of parallel fetch threads |
| `--max N` | *(none)* | Limit fetch to N games (testing) |
| `--refresh` | off | Ignore cache, re-fetch everything |
| `--news-age HOURS` | `24` | Re-fetch news for games whose cached news is older than N hours |
| `--no-wishlist` | off | Skip wishlist fetch |
| `--followed` | off | Fetch followed games (opt-in, see note) |
| `--lang` | *(system)* | Force interface language (`en`, `fr`, …). Defaults to the system locale, falls back to `en`. |
| `-v` / `--verbose` | off | Enable DEBUG logging |

**Epic Games options:**

| Option | Default | Description |
|---|---|---|
| `--epic-auth-code` | *(none)* | One-time Epic authorization code (first login) |
| `--epic-device-id` | *(none)* | Epic device ID (persistent auth) |
| `--epic-account-id` | *(none)* | Epic account ID (persistent auth) |
| `--epic-device-secret` | *(none)* | Epic device secret (persistent auth) |
| `--twitch-client-id` | *(none)* | Twitch/IGDB client ID (better AppID resolution) |
| `--twitch-client-secret` | *(none)* | Twitch/IGDB client secret |

> **Note on `--followed`**: the Steam Web API no longer returns followed games with a standard key. This flag is available but will generally return an empty list.

---

## 6. Navigating the interface

### Library page (`steam_library.html`)

**Toolbar — main row (always visible):**
- **Search** — filters games by name in real time (`/` or `Ctrl+K`)
- **Sort** — by name, Metacritic score, playtime, release date, last update, last news date
- **⚙ Filters** — expands/collapses the filter panel; a badge shows the number of active filters
- **Reset** — clears all filters and search (only appears when something is active)
- **☰ Liste / ⊞ Grille** — toggle between card grid and table list view
- **🗞 News** — opens the news feed page (carries compatible filters via URL hash)

**Filter panel (collapsible):**

| Group | Options |
|---|---|
| **Statut** | All · Early Access · Released · Upcoming |
| **Source** | 🎮 All · Owned · 🎁 Wishlist · 👁 Followed · 🎮 Epic |
| **Type news** | All types · 📋 Patch notes · 📰 News |
| **Temps de jeu** | All · Never played · < 1 h · 1–10 h · > 10 h |
| **Metacritic** | All · No score · < 50 · 50–75 · > 75 |
| **Recent update** | All · 2 days · 5 days · 15 days · 30 days (based on last patch note date) |

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
- Same two-layer toolbar: search + sort in the main row, Status and Type news filters in the collapsible panel
- Type badge on each row (green for `patchnotes`, grey for others)
- Live result counter
- Click a row to open the news item on Steam

---

## 7. Cache strategy & refresh

| Scenario | Behaviour |
|---|---|
| New game (never seen) | App details + news fetched |
| Cached game, news < `--news-age` hours old | Skipped entirely |
| Cached game, news ≥ `--news-age` hours old | News re-fetched, app details preserved |
| `--refresh` flag set | Everything re-fetched, cache ignored |

**Tip:** run `steampulse.exe` daily without extra flags to keep news up to date. Use `--refresh` only when game metadata has changed (price update, leaving Early Access, etc.).

---

## 8. Advanced usage — separate steps

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

## 9. FAQ

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
