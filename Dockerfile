# One container, four processes (see deploy/supervisord.conf):
#
#   ┌──────────────────────────── container ─────────────────────────────┐
#   │  edge (Caddy, :$PORT) ─┬─ /ws, /realtime/* ─► realtime  (127.0.0.1:8002) ──┐
#   │                        └─ everything else  ─► gateway   (127.0.0.1:8001) ──┤ gRPC
#   │                                                engine    (127.0.0.1:50051) ◄┘
#   └────────────────────────────────────────────────────────────────────┘
#
# Render's free plan gives one web service and one public port, so the three microservices share
# the container and only the edge proxy is exposed. Each one is still an independent process with
# its own entry point, restart policy and log prefix, and could move to its own container by
# changing addresses in the environment.

FROM caddy:2.10.2-alpine AS caddy

FROM python:3.12.8-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=10000 \
    MALLOC_ARENA_MAX=2 \
    XDG_CONFIG_HOME=/tmp/caddy-config \
    XDG_DATA_HOME=/tmp/caddy-data

WORKDIR /app

COPY requirements.txt requirements-deploy.txt ./
RUN pip install -r requirements.txt -r requirements-deploy.txt

COPY --from=caddy /usr/bin/caddy /usr/local/bin/caddy

COPY alembic.ini ./
COPY alembic ./alembic
COPY data ./data
COPY deploy ./deploy
COPY volcano ./volcano

RUN useradd --system --uid 10001 --home-dir /app volcano && chown -R volcano /app
USER volcano

EXPOSE 10000
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health', timeout=4)"

ENTRYPOINT ["sh", "deploy/entrypoint.sh"]
