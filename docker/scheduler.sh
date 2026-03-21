#!/bin/bash
# Periodic fetch loop — credentials and settings come from /run/steampulse/config.toml,
# which is written by entrypoint.sh from env vars or a mounted config file.
set -euo pipefail

_RAW_INTERVAL="${INTERVAL_HOURS:-4}"
if ! [[ "$_RAW_INTERVAL" =~ ^[1-9][0-9]*$ ]]; then
    echo "[SteamPulse] WARNING: INTERVAL_HOURS=${_RAW_INTERVAL@Q} is not a positive integer; defaulting to 4." >&2
    _RAW_INTERVAL=4
fi
INTERVAL_SECONDS=$(( _RAW_INTERVAL * 3600 ))

while true; do
    args=(
        steampulse
        --config /run/steampulse/config.toml
        --db     /data/steam_library.db
        --output /data/steam_library.html
    )
    [ "${REFRESH:-false}" = "true" ] && args+=(--refresh)

    echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Starting SteamPulse fetch…"
    "${args[@]}" \
        && echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Fetch complete." \
        || echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] WARNING: fetch exited with an error."

    # Persist updated config (Epic refresh tokens may have been rotated).
    cp /run/steampulse/config.toml /data/.config_persisted.toml 2>/dev/null || true

    echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Next run in ${_RAW_INTERVAL}h (${INTERVAL_SECONDS}s)."
    sleep "$INTERVAL_SECONDS"
done
