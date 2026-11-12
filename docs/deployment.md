# Deployment guide

## Moving the existing Render service to v3

v3 changes the service from the `python` runtime to `docker`. Production keeps running the old version
until you switch; nothing changes when the branch is merged unless Render deploys it.

1. **Back up the database** (Neon → Branches → create a branch from `main`). Migration 0004 is one-way.
2. Merge `refactor/microservices` into `main` (or point Render at the branch to try it first).
3. Render → the service → **Settings → Runtime: Docker**, Dockerfile path `./Dockerfile`, root directory
   empty (the backend now lives at the repository root). Alternatively re-create it from `render.yaml`.
   Set **Health Check Path** to `/live` (see "Staying awake on the free plan" below).
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

## Staying awake on the free plan

Render's free plan spins a web service down after 15 minutes without inbound traffic and needs about a
minute to start it again; a serverless PostgreSQL such as Neon suspends after 5 idle minutes and has a
monthly compute allowance. The service is built around both limits:

| Concern | How it is handled |
|---|---|
| The service sleeping | The realtime service requests its own public URL every 10 minutes (`KEEP_AWAKE`, on by default wherever `RENDER_EXTERNAL_URL` exists). An open, visible browser tab also counts: the frontend sends a WebSocket ping every few minutes. |
| Waking it up again | Only an outside request can (after a deploy, a restart, or outside `KEEP_AWAKE_HOURS`). The `Keep alive` workflow is that backup; GitHub runs it on a best-effort schedule, often hours late, so do not rely on it alone. An external uptime monitor pointed at `/live` every 5 minutes is a more punctual backup. |
| Not wasting database compute | `/live` (health check, keep-awake, wake-up) never queries the database. The engine only polls the alerts while a browser is subscribed; an idle service runs no queries at all. Use `/health` when you do want to check the database. |
| Free instance hours | Render grants 750 per workspace and month — enough for ONE service awake around the clock. With more free services in the workspace set `KEEP_AWAKE_HOURS` (e.g. `6-23`, Colombia time) or `KEEP_AWAKE=false`; when the hours run out Render suspends every free service until next month. |
| A slow start | The engine runs at a lower CPU priority so the API answers first; the engine reports "unavailable" for the first seconds and the frontend retries by itself. |
| A service that cannot start | The container exits within seconds (`deploy/fail_fast.py`) and the log names the service, instead of a deploy that times out after 15 minutes. |

A paid instance does not sleep and removes the need for all of the above.

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

New: `REALTIME_INTERNAL_URL`, `REALTIME_MAX_CONNECTIONS`, `REALTIME_HEARTBEAT_S`, `KEEP_AWAKE`,
`KEEP_AWAKE_URL` (defaults to Render's `RENDER_EXTERNAL_URL`), `KEEP_AWAKE_INTERVAL_S`, `KEEP_AWAKE_HOURS`,
`LOCAL_UTC_OFFSET_HOURS`.

## API changes for clients

All routes, JSON fields and enum values are English now (see `docs/glossary.md`), e.g.
`/alertas/activas` → `/alerts/active`, `nivel_riesgo: "ROJO"` → `risk_level: "RED"`. Live alerts and the
simulator moved from `GET /motor/alertas/eventos` (SSE) and `WS /motor/simulador` to the realtime hub
(`WS /ws`). The frontend in `volcanoFront` is updated accordingly; the frontend revalidation route is
`/api/revalidate` (`REVALIDATE_SECRET` on both sides).
