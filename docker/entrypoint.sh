#!/bin/bash
# Container entry point:
# 1. Build /data/config.toml from env vars, OR copy a mounted /config/config.toml
# 2. Create a placeholder HTML page if the data directory is empty
# 3. Hand off to supervisord
set -euo pipefail

CONFIG_DEST=/data/config.toml

if [ -f /config/config.toml ]; then
    # ── A config file was mounted: use it directly ───────────────────────────
    echo "[SteamPulse] Using mounted config file /config/config.toml"
    cp /config/config.toml "$CONFIG_DEST"
else
    # ── Generate config.toml from environment variables ──────────────────────
    # STEAM_API_KEY and STEAM_ID are required when no config file is mounted.
    if [ -z "${STEAM_API_KEY:-}" ]; then
        echo "ERROR: STEAM_API_KEY is required (or mount a config.toml at /config/config.toml)." >&2
        exit 1
    fi
    if [ -z "${STEAM_ID:-}" ]; then
        echo "ERROR: STEAM_ID is required (or mount a config.toml at /config/config.toml)." >&2
        exit 1
    fi

    # Python handles TOML escaping properly for all secret values.
    python3 - << 'PYEOF'
import os


def q(v: str) -> str:
    """Escape a string value for inline TOML."""
    return v.replace("\\", "\\\\").replace('"', '\\"')


lines = [
    "[steam]",
    f'key     = "{q(os.environ["STEAM_API_KEY"])}"',
    f'steamid = "{q(os.environ["STEAM_ID"])}"',
]

epic_token = os.environ.get("EPIC_REFRESH_TOKEN", "")
epic_id    = os.environ.get("EPIC_ACCOUNT_ID", "")
if epic_token and epic_id:
    lines += [
        "",
        "[epic]",
        f'refresh_token = "{q(epic_token)}"',
        f'account_id    = "{q(epic_id)}"',
    ]

twitch_id     = os.environ.get("TWITCH_CLIENT_ID", "")
twitch_secret = os.environ.get("TWITCH_CLIENT_SECRET", "")
if twitch_id and twitch_secret:
    lines += [
        "",
        "[twitch]",
        f'client_id     = "{q(twitch_id)}"',
        f'client_secret = "{q(twitch_secret)}"',
    ]

workers  = os.environ.get("WORKERS", "4")
news_age = os.environ.get("NEWS_AGE", "24")
lang     = os.environ.get("SP_LANG", "")
lines += [
    "",
    "[settings]",
    'db       = "/data/steam_library.db"',
    f"workers  = {workers}",
    f"news_age = {news_age}",
]
if lang:
    lines.append(f'lang     = "{q(lang)}"')

with open("/data/config.toml", "w") as f:
    f.write("\n".join(lines) + "\n")

print("[SteamPulse] config.toml generated from environment variables.")
PYEOF
fi

# ── Create a placeholder page so nginx returns 200 before the first fetch ───
if [ ! -f /data/steam_library.html ]; then
    cat > /data/steam_library.html << 'HTMLEOF'
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>SteamPulse — Loading…</title>
  <meta http-equiv="refresh" content="30">
  <style>
    body { font-family: sans-serif; text-align: center; padding: 4rem;
           background: #1b2838; color: #c6d4df; }
    h1   { color: #66c0f4; font-size: 2rem; margin-bottom: 1rem; }
    p    { opacity: .8; }
  </style>
</head>
<body>
  <h1>🚀 SteamPulse</h1>
  <p>First data fetch is in progress — this can take 15–30 minutes for a large library.</p>
  <p>This page will refresh automatically every 30 seconds.</p>
</body>
</html>
HTMLEOF
fi

exec /usr/bin/supervisord -c /etc/supervisor/conf.d/steampulse.conf
