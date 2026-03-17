# SteamPulse — Docker image
# Single container: nginx (serves HTML) + supervisord (process manager) + scheduler (loop)
#
# Build:
#   docker build -t steampulse -f docker/Dockerfile .
#
# Run (see docker-compose.yml for full options):
#   docker run -p 8080:80 \
#     -e STEAM_API_KEY=xxx -e STEAM_ID=xxx \
#     -v steampulse_data:/data \
#     steampulse

FROM python:3.13-slim

# -- System dependencies -------------------------------------------------------
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        nginx \
        supervisor \
        curl \
 && rm -rf /var/lib/apt/lists/*

# -- Install SteamPulse --------------------------------------------------------
WORKDIR /build
COPY pyproject.toml README.md ./
COPY steam_tracker/ ./steam_tracker/
RUN pip install --no-cache-dir . \
 && rm -rf /build

# -- nginx: serve /data on port 80 --------------------------------------------
COPY docker/nginx.conf /etc/nginx/sites-available/steampulse
RUN rm -f /etc/nginx/sites-enabled/default \
 && ln -s /etc/nginx/sites-available/steampulse /etc/nginx/sites-enabled/steampulse

# -- supervisord: manage nginx + scheduler ------------------------------------
COPY docker/supervisord.conf /etc/supervisor/conf.d/steampulse.conf

# -- Runtime scripts -----------------------------------------------------------
COPY docker/entrypoint.sh /entrypoint.sh
COPY docker/scheduler.sh  /scheduler.sh
RUN chmod +x /entrypoint.sh /scheduler.sh

# -- Data volume (SQLite DB + generated HTML pages) ---------------------------
RUN mkdir -p /data
VOLUME ["/data"]

# -- Health check: HTTP 200 on port 80 ----------------------------------------
HEALTHCHECK --interval=60s --timeout=5s --start-period=120s \
    CMD curl -sf http://localhost/ > /dev/null || exit 1

EXPOSE 80
WORKDIR /data
ENTRYPOINT ["/entrypoint.sh"]
