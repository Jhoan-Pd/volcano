#!/usr/bin/env sh
# Arranque del servicio en Render: un solo servicio web con dos procesos.
#
#   ┌──────────── servicio predictor-brotes-api ─────────────┐
#   │  uvicorn (público, $PORT)  ──gRPC──►  motor (127.0.0.1) │
#   └─────────────────────────────────────────────────────────┘
#
# 1. Migraciones y seed idempotente (el plan gratis no tiene "pre-deploy").
# 2. Motor gRPC en segundo plano, con un bucle que lo reinicia si se cae.
# 3. Se espera al chequeo de salud de gRPC y se arranca uvicorn como proceso principal.
#    Si el motor no responde a tiempo, la API arranca igual: sus endpoints /motor responden 503.
set -e

alembic upgrade head
python -m app.seed

(
  while true; do
    python -m app.motor.servidor || echo "El motor gRPC terminó con error; se reinicia en 3 s"
    sleep 3
  done
) &

python -m app.motor.salud 90 || echo "Se continúa sin el motor gRPC"

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
