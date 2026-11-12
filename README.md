# Volcano · disease outbreak predictor (backend)

Early-warning platform for Pasto and the Galeras volcano area (Nariño, Colombia). It combines **public
signals** — weather, symptom searches, pharmacy sales and volcanic activity — to forecast acute respiratory
infections (IRA), acute diarrhoeal disease (EDA), dengue and ash-related respiratory illness four weeks
ahead, and raises **early alerts**.

> *Proyecto final de Programación Orientada a la Web.* The user interface is in Spanish (repository
> [`volcanoFront`](https://github.com/Jhoan-Pd/volcanoFront)); all code, contracts and data names are in
> English. [`docs/glossary.md`](docs/glossary.md) maps every domain term between the two languages.

| | |
|---|---|
| **Services** | `gateway` (FastAPI, REST + SSE) · `engine` (gRPC, scikit-learn) · `realtime` (WebSocket hub) · `edge` (Caddy) |
| **Stack** | Python 3.12 · FastAPI · grpcio · SQLAlchemy 2 · Pydantic 2 · Alembic · scikit-learn · pandas · ReportLab |
| **Data** | PostgreSQL (Neon) in production · SQLite for quick local runs and tests |
| **Runtime** | One Docker container on Render (free plan) · GitHub Actions for CI, the daily update and keep-alive |

## Architecture

```
                         ┌──────────────────────── container (Render) ─────────────────────────┐
 browser ── HTTPS ──────►│ edge · Caddy :$PORT                                                 │
 (Next.js on Vercel)     │   ├─ /ws, /realtime/* ─► realtime  ─┐  WatchAlerts (1 stream for     │
                         │   │   WebSocket hub      :8002      │  every browser), Simulate…    │
                         │   └─ everything else ──► gateway  ──┤  gRPC + token                 │
                         │       REST · SSE         :8001      ▼                               │
                         │                           engine · gRPC :50051 (loopback only)      │
                         │                           models in memory · training · alert feed │
                         └──────────────────────────────┬─────────────────────────────────────┘
                                                        ▼
                     PostgreSQL (Neon) · Open-Meteo · Google Trends · datos.gov.co · Resend
```

Each microservice is its own process with its own entry point and restart policy (supervisord), and could
move to its own container by changing addresses in the environment. Only the edge proxy is public.

| Service | Owns | Talks to the browser with | Talks to the engine with |
|---|---|---|---|
| **gateway** | auth (JWT, roles), CRUD, dashboard reads, reports, CSV import, daily job | JSON, SSE (training progress) | unary + server-streaming + client-streaming gRPC |
| **engine** | models in memory, training, forecasts, what-if scenarios, bulk uploads, alert feed | — | (server) all four RPC types |
| **realtime** | WebSocket connections, subscriptions, presence, fan-out, back-pressure | one multiplexed WebSocket | server-streaming (`WatchAlerts`) + bidirectional (`SimulateScenarios`) |

Details — gRPC contract, WebSocket protocol, reconnection, memory budget — are in
[`docs/architecture.md`](docs/architecture.md).

## Repository layout

```
volcano/
├── shared/          config, domain errors, epidemiological weeks, logging, security
├── db/ models/      SQLAlchemy base, 13 tables, enums (lazy package: enums load without SQLAlchemy)
├── schemas/         Pydantic input/output shapes
├── repositories/    generic repository + one per entity
├── sources/         Open-Meteo, Google Trends (+ CSV fallback), SIVIGILA (Socrata), pharmacy index
├── ml/              features, leak-free dataset, estimators (Strategy), trainer, forecaster, explainer
├── services/        use cases; only `forecasting` and `training` import the ML stack (engine only)
├── notifications/   e-mail (Resend), frontend revalidation, realtime events
├── rpc/             generated gRPC code, protobuf ↔ domain mapping, error mapping, clients
├── gateway/         FastAPI app, routers, dependencies, HTTP error handlers
├── engine/          gRPC server, servicer, interceptors, model cache, alert feed, start-up check
├── realtime/        WebSocket hub: protocol, hub, alert relay, simulation sessions
└── seed/            idempotent seed (catalogues, demo users, simulated history)
proto/volcano/engine/v1/engine.proto      the engine's contract
alembic/versions/                         0001-0003 historical schema · 0004 English schema
deploy/                                   entrypoint, supervisord, Caddyfile
tests/                                    131 tests (unit, API, real gRPC server, WebSocket end to end, migrations)
scripts/                                  generate_grpc.sh · smoke_test.py
```

## Running it

**Everything, like production** (Docker):

```bash
docker compose up --build
python scripts/smoke_test.py http://localhost:10000      # REST → gRPC, WebSocket → gRPC, edge rules
```

**Each service by hand** (Python 3.12):

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                       # SQLite by default
alembic upgrade head && python -m volcano.seed --train
python -m volcano.engine.server                                   # gRPC on 127.0.0.1:50051
uvicorn volcano.gateway.app:app --port 8001 --reload              # REST  → http://localhost:8001/docs
uvicorn volcano.realtime.app:app --port 8002                      # WS    → ws://localhost:8002/ws
```

**Quality gates** (the same as CI):

```bash
ruff check volcano tests alembic scripts
bash scripts/generate_grpc.sh && git diff --exit-code volcano/rpc   # generated code matches the .proto
alembic upgrade head && alembic check                                # models and migrations agree
pytest
```

Demo users: `admin@predictor.co` (ADMIN), `farmacia@demo.co` (PHARMACY), `ciudadano@demo.co` (CITIZEN);
passwords come from `ADMIN_PASSWORD` and `DEMO_PASSWORD`.

## Main endpoints

| Area | Endpoints (prefix `/api/v1`) |
|---|---|
| Auth | `POST /auth/login` · `POST /auth/signup` · `GET /auth/me` |
| Dashboard (public) | `/dashboard/summary` · `/series` · `/municipality-risk` · `/volcano` · `/prediction` · `/explanation` |
| Alerts | `GET /alerts/active` · `GET /alerts/search` (public) · `POST /alerts/evaluate` · `PATCH /alerts/{id}/close` |
| Engine bridge | `GET /engine/status` · `GET /engine/forecast` · `POST /engine/training` (SSE) · `POST /engine/pharmacy-upload` |
| Model | `POST /model/retrain` · `GET /model/status` · `POST /model/predict` · `GET /model/history` |
| Pharmacies | `/pharmacy/me` · `/pharmacy/reports[/{year}/{week}]` · `/pharmacy/sales-index` |
| Data | `/data/trends[/sync]` · `/data/sivigila/sync` · `/data/import/{cases,weather,events,trends}` · `/data/status` |
| Catalogues | `/municipalities` · `/diseases` · `/pharmacies` · `/volcanic-events` · `/users` |
| Reports | `/reports/cases.csv` · `/predictions.csv` · `/alerts.csv` · `/summary.pdf` |
| Jobs | `POST /jobs/daily-update` (header `X-Cron-Secret`) |
| Health | `/live` (liveness, no database) · `/health` (readiness: database) · `/health/services` (the three microservices) |
| Realtime | `WS /ws` · `GET /realtime/health` |

Errors always have the same shape: `{"error": {"code": "NOT_FOUND", "message": "…", "details": …}}` —
`code` is stable English, `message` is Spanish for the user.

## How the forecast works

1. **Dataset without leakage** (`ml/dataset.py`): one row per municipality and epidemiological week with
   what is known when the week closes — case lags, seasonality, lagged weather, searches, pharmacy sales,
   SO₂ and ash fall; targets are the cases of t+1 … t+4.
2. **Temporal validation** (`ml/trainer.py`): the last 52 weeks are the test set; a moving-average
   baseline competes with Random Forest and Gradient Boosting (one model per horizon). The winner is
   retrained on all the data; the 80 % interval comes from the test residuals.
3. **Traffic light** (`services/risk.py`): endemic channel with percentiles 50/75/90 of the same weeks of
   the previous five years, per disease.
4. **Explainability** (`ml/explainer.py`): group occlusion — how many cases each signal group adds.
5. **Alerts** (`services/alerts.py`): observed or predicted ORANGE/RED, idempotent, closed automatically,
   e-mailed once, and pushed live to every open dashboard through the realtime hub.

Production metrics (last 52 weeks): MAE 16-22 % lower than the moving average for every disease.

## Deployment

Render runs the Docker image (`render.yaml`, runtime `docker`); Vercel serves the frontend; Neon hosts
PostgreSQL. The step-by-step guide, the variables renamed in v3 (old names still work) and the database
migration are in [`docs/deployment.md`](docs/deployment.md).
