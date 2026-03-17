#!/bin/bash
# Periodic fetch loop — credentials and settings come from /data/config.toml,
# which is written by entrypoint.sh from env vars or a mounted config file.
set -euo pipefail

INTERVAL_SECONDS=$(( ${INTERVAL_HOURS:-4} * 3600 ))

while true; do
    args=(
        steampulse
        --config /data/config.toml
        --db     /data/steam_library.db
        --output /data/steam_library.html
    )
    [ "${REFRESH:-false}" = "true" ] && args+=(--refresh)

    echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Starting SteamPulse fetch…"
    "${args[@]}" \
        && echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Fetch complete." \
        || echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] WARNING: fetch exited with an error."

    echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Next run in ${INTERVAL_HOURS:-4}h (${INTERVAL_SECONDS}s)."
    sleep "$INTERVAL_SECONDS"
done
