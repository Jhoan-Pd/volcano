# Deployment guide

## Moving the existing Render service to v3

v3 changes the service from the `python` runtime to `docker`. Production keeps running the old version
until you switch; nothing changes when the branch is merged unless Render deploys it.

1. **Back up the database** (Neon → Branches → create a branch from `main`). Migration 0004 is one-way.
2. Merge `refactor/microservices` into `main` (or point Render at the branch to try it first).
3. Render → the service → **Settings → Runtime: Docker**, Dockerfile path `./Dockerfile`, root directory
   empty (the backend now lives at the repository root). Alternatively re-create it from `render.yaml`.
4. **Environment** — nothing is mandatory to rename, because the old names are still accepted, but add:
   - `INTERNAL_TOKEN` (any long random value; `MOTOR_GRPC_TOKEN` is used if present),
   - `ENGINE_GRPC_THREADS=16`.
5. Deploy. On start the container runs `alembic upgrade head` (0004 translates the data), the seed (no-op
   on an existing database) and the four processes. The engine retrains the four models in the background
   (a few minutes); the dashboard works meanwhile with the stored predictions.
6. Check: `https://<service>.onrender.com/health/services` must show the three services available, and
   `python scripts/smoke_test.py https://<service>.onrender.com` must pass.
7. Point the frontend (repository `volcanoFront`) at the same URL and deploy it on Vercel.
8. The GitHub Actions cron now calls `POST /api/v1/jobs/daily-update`; the secrets `API_URL` and
   `CRON_SECRET` stay the same.

## Variables renamed in v3

| New name | Old name (still accepted) |
|---|---|
| `INTERNAL_TOKEN` | `MOTOR_GRPC_TOKEN`, `ENGINE_GRPC_TOKEN` |
| `ENGINE_GRPC_ADDRESS` | `MOTOR_GRPC_DIRECCION` |
| `ENGINE_GRPC_TIMEOUT_S` | `MOTOR_GRPC_TIMEOUT_S` |
| `ENGINE_GRPC_THREADS` | `MOTOR_GRPC_HILOS` |
| `ENGINE_ALERT_POLL_S` | `MOTOR_INTERVALO_ALERTAS_S` |
| `ENGINE_CACHE_TTL_S` | `MOTOR_CACHE_TTL_S` |
| `TRAIN_ON_STARTUP` | `ENTRENAR_AL_INICIO` |
| `SEED_REAL_WEATHER` | `SEED_CLIMA_REAL` |
| `SEED_START_YEAR` | `SEED_ANIO_INICIO` |
| `SIVIGILA_DEPARTMENT` | `SIVIGILA_DEPARTAMENTO` |
| `TRENDS_ENABLED` | `TRENDS_HABILITADO` |
| `TRENDS_PAUSE_SECONDS` | `TRENDS_PAUSA_SEGUNDOS` |
| `HTTP_TIMEOUT_SECONDS` | `HTTP_TIMEOUT_SEGUNDOS` |
| `ALERT_EMAIL_SENDER` | `ALERTAS_EMAIL_REMITENTE` |
| `ALERT_EMAIL_RECIPIENTS` | `ALERTAS_EMAIL_DESTINO` |
| `ALERTS_TO_CITIZENS` | `ALERTAS_A_CIUDADANOS` |
| `REVALIDATE_SECRET` | `REVALIDAR_SECRET` |
| `ADMIN_NAME` | `ADMIN_NOMBRE` |

New: `REALTIME_INTERNAL_URL`, `REALTIME_MAX_CONNECTIONS`, `REALTIME_HEARTBEAT_S`.

## API changes for clients

All routes, JSON fields and enum values are English now (see `docs/glossary.md`), e.g.
`/alertas/activas` → `/alerts/active`, `nivel_riesgo: "ROJO"` → `risk_level: "RED"`. Live alerts and the
simulator moved from `GET /motor/alertas/eventos` (SSE) and `WS /motor/simulador` to the realtime hub
(`WS /ws`). The frontend in `volcanoFront` is updated accordingly; the frontend revalidation route is
`/api/revalidate` (`REVALIDATE_SECRET` on both sides).
