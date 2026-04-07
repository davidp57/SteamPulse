# SteamPulse

🇬🇧 [English](#-english) · 🇫🇷 [Français](#-français)

---

## 🇬🇧 English

> Fetches your Steam library, wishlist, and game news via the Steam API and renders them as a filterable offline HTML dashboard.

```
steampulse.exe  →  Steam API  →  SQLite  →  steam_library.html
                                          →  steam_alerts.html
```

### Features

- **Library + Wishlist** — owned games, wishlist and followed games in a single view
- **Multi-store** — Epic Games library imported alongside Steam; games resolved to Steam AppIDs when possible
- **Configurable alerts** — rule-based alert system (price drop, major update, new DLC, review changes…) with read/unread tracking; replaces the old news page
- **Smart cache** — app details only re-fetched for new games; news refreshed after 24 h (configurable)
- **Static HTML** — filterable/sortable cards by source, status, genre, Metacritic, playtime; no server required
- **Multilingual** — UI in English or French; auto-detected from system locale, or forced with `--lang`
- **Quality** — ruff, strict mypy, pytest (473 tests)

### Quick start

**Option A — Standalone executable (Windows, no Python required)**

Download `steampulse.exe` from the [latest release](../../releases/latest), then:

```
steampulse.exe --key <API_KEY> --steamid <STEAMID64>
```

**Option B — From source (Python 3.11+)**

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # Linux / macOS
pip install -e .
steampulse --key <API_KEY> --steamid <STEAMID64>
```

- API key → <https://steamcommunity.com/dev/apikey>
- SteamID64 → <https://steamid.io>

Open `steam_library.html` in a browser — no server required.

**Option C — Docker (NAS / server / always-on)**

A pre-built image is available on GHCR. It runs a periodic fetch and serves the dashboard on port 80:

```bash
# 1. Run steampulse.exe once on Windows to generate config.toml
#    (%APPDATA%\steampulse\config.toml)
# 2. Download docker-compose.yml from the latest release and place
#    config.toml next to it, then:
docker compose up -d
# → open http://localhost:8080
```

Download `docker-compose.yml`: <https://github.com/davidp57/SteamPulse/releases/latest/download/docker-compose.yml>

See [docs/en/user-guide.md — Section 12](docs/en/user-guide.md#12-docker-deployment) for the full guide (Epic credentials, Synology NAS, Portainer).

### Documentation

| Document | 🇬🇧 English | 🇫🇷 Français |
|---|---|---|
| User guide | [docs/en/user-guide.md](docs/en/user-guide.md) | [docs/fr/user-guide.md](docs/fr/user-guide.md) |
| Developer guide | [docs/en/developer-guide.md](docs/en/developer-guide.md) | [docs/fr/developer-guide.md](docs/fr/developer-guide.md) |
| Changelog | [CHANGELOG.md](CHANGELOG.md) | [CHANGELOG.md](CHANGELOG.md) |

---

## 🇫🇷 Français

> Récupère ta bibliothèque Steam, ta wishlist et les actualités de tes jeux via l'API Steam, et les affiche dans un dashboard HTML filtrable hors ligne.

```
steampulse.exe  →  API Steam  →  SQLite  →  steam_library.html
                                          →  steam_alerts.html
```

### Fonctionnalités

- **Bibliothèque + Wishlist** — jeux possédés, wishlist et jeux suivis regroupés dans une seule vue
- **Multi-store** — bibliothèque Epic Games importée aux côtés de Steam ; jeux résolus vers des AppIDs Steam si possible
- **Alertes configurables** — système d'alertes basé sur des règles (baisse de prix, mise à jour majeure, nouveau DLC, évolution des avis…) avec suivi lu/non lu ; remplace l'ancienne page news
- **Cache intelligent** — app_details rechargées uniquement pour les nouveaux jeux ; news rafraîchies après 24 h (configurable)
- **HTML statique** — cartes filtrables/triables par source, statut, genre, Metacritic, temps de jeu ; aucun serveur requis
- **Multilingue** — interface en anglais ou en français ; détectée automatiquement ou forcée avec `--lang`
- **Qualité** — ruff, mypy strict, pytest (473 tests)

### Guide rapide

**Option A — Exécutable standalone (Windows, sans Python)**

Télécharge `steampulse.exe` depuis la [dernière release](../../releases/latest), puis :

```
steampulse.exe --key <API_KEY> --steamid <STEAMID64>
```

**Option B — Depuis les sources (Python 3.11+)**

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # Linux / macOS
pip install -e .
steampulse --key <API_KEY> --steamid <STEAMID64>
```

- Clé API → <https://steamcommunity.com/dev/apikey>
- SteamID64 → <https://steamid.io>

Ouvre `steam_library.html` dans un navigateur — aucun serveur requis.

**Option C — Docker (NAS / serveur / machine permanente)**

Une image préconstruite est disponible sur GHCR. Elle lance un fetch périodique et sert le dashboard sur le port 80 :

```bash
# 1. Lance steampulse.exe une fois sur Windows pour générer config.toml
#    (%APPDATA%\steampulse\config.toml)
# 2. Télécharge docker-compose.yml depuis la dernière release et place
#    config.toml à côté, puis :
docker compose up -d
# → ouvre http://localhost:8080
```

Télécharge `docker-compose.yml` : <https://github.com/davidp57/SteamPulse/releases/latest/download/docker-compose.yml>

Voir [docs/fr/user-guide.md — Section 12](docs/fr/user-guide.md#12-déploiement-docker) pour le guide complet (credentials Epic, NAS Synology, Portainer).

### Documentation

| Document | 🇬🇧 English | 🇫🇷 Français |
|---|---|---|
| User guide | [docs/en/user-guide.md](docs/en/user-guide.md) | [docs/fr/user-guide.md](docs/fr/user-guide.md) |
| Developer guide | [docs/en/developer-guide.md](docs/en/developer-guide.md) | [docs/fr/developer-guide.md](docs/fr/developer-guide.md) |
| Changelog | [CHANGELOG.md](CHANGELOG.md) | [CHANGELOG.md](CHANGELOG.md) |
