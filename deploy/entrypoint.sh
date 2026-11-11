#!/usr/bin/env sh
# Container start-up.
#
# 1. Migrations and the idempotent seed (Render's free plan has no pre-deploy step). They run once,
#    here, before any service starts, so the three services never race to migrate.
# 2. supervisord becomes PID 1 and starts the engine, the gateway, the realtime hub and the edge
#    proxy, restarting any of them that crashes. SIGTERM from Render reaches supervisord, which stops
#    them in reverse priority order.
#
# If the engine is still loading, the gateway answers its endpoints with 503 and the realtime hub
# keeps retrying its upstream stream; the rest of the site works meanwhile.
set -e

alembic upgrade head
python -m volcano.seed

exec supervisord -c deploy/supervisord.conf
