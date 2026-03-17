# feat: Docker deployment

## Summary

Adds a self-contained Docker image that runs SteamPulse on a schedule and serves the generated HTML pages via nginx — deployable on any Docker engine (Synology NAS, home server, VPS, etc.) with a single `docker compose up -d`.

## Changes

### New files

| File | Description |
|---|---|
| `docker/Dockerfile` | Python 3.13-slim + nginx + supervisord; installs SteamPulse via `pip install .` |
| `docker/nginx.conf` | Serves `/data` on port 80; blocks direct access to `.db` files |
| `docker/supervisord.conf` | Manages nginx + scheduler as two supervised processes |
| `docker/entrypoint.sh` | Generates `config.toml` from env vars **or** copies a mounted config file; creates a loading placeholder page; starts supervisord |
| `docker/scheduler.sh` | Fetch loop: `steampulse --config /data/config.toml …`; no secrets in process args |
| `docker-compose.yml` | Ready-to-use Compose file; explicit config-mount option commented in |
| `.env.example` | Template for all supported environment variables |
| `.dockerignore` | Excludes `.venv/`, `tests/`, `*.db`, `*.html`, etc. from the build context |
| `.github/workflows/docker.yml` | Publishes image to GHCR (`ghcr.io/davidp57/steampulse`) on every `v*` tag and `main` push |
| `.gitattributes` | Forces LF line endings for `*.sh` and `docker/Dockerfile` to prevent CRLF breakage when built on Windows machines |

### Updated files

- `docs/en/user-guide.md`, `docs/fr/user-guide.md` — new **Section 12: Docker deployment** with both configuration options, environment variable reference, Synology NAS examples, and useful commands
- `CHANGELOG.md` — Docker entries under `[Unreleased]`

## Architecture

```
Container
├── nginx           → serves  /data/*.html on :80
└── scheduler loop  → steampulse --config /data/config.toml  (every INTERVAL_HOURS)

/data  (named volume, persisted)
├── config.toml         ← generated at startup from env vars or copied from mount
├── steam_library.db    ← SQLite database
├── steam_library.html  ← generated HTML (library)
└── steam_news.html     ← generated HTML (news feed)
```

## Two configuration approaches

### Option A — Environment variables (Steam-only, simplest)
```bash
cp .env.example .env   # fill in STEAM_API_KEY + STEAM_ID
docker compose up -d
```
`entrypoint.sh` generates a `config.toml` at startup from the env vars (using Python for correct TOML escaping of secret values).

### Option B — Mounted config file (recommended for Epic + Twitch)
```bash
# On a machine with SteamPulse installed:
steam-setup           # handles Epic OAuth2 browser flow, writes config.toml
cp ~/.config/steampulse/config.toml ./config.toml

# Uncomment in docker-compose.yml:
#   - ./config.toml:/config/config.toml:ro

docker compose up -d
```
When a file is mounted at `/config/config.toml`, credential env vars are ignored.  
Scheduling variables (`INTERVAL_HOURS`, `REFRESH`) are always read from the environment.

> **Why not run the wizard inside the container?** The wizard requires an interactive terminal + browser for Epic OAuth2 — neither available in an unattended container. The standalone `steampulse.exe` handles the complex browser flow once; the resulting `config.toml` is portable and mounts cleanly into Docker.

## Security notes

- Secrets are written to a `config.toml` file inside the volume — **never exposed as process arguments** (visible in `ps aux`)
- `.env` is in `.gitignore` / `.dockerignore`; `config.toml` mount is read-only (`:ro`)
- nginx blocks direct access to `.db` files
- GHCR workflow uses `secrets.GITHUB_TOKEN` (no manual PAT required)

## Testing

No new Python tests (all Docker artefacts are shell/config files). Existing suite: **217 passed, 2 skipped**.

To manually verify the image builds correctly:
```bash
docker build -t steampulse-test -f docker/Dockerfile .
```
