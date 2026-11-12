# Architecture

## Why three services in one container

The free plans available to the project (Render: one web service, one public port, 512 MB) rule out
one container per service. The code is nevertheless split along real service boundaries:

- **gateway** — the public REST API. Stateless HTTP work that needs the database but no ML.
- **engine** — the only process that loads scikit-learn and pandas. Long-lived, keeps trained models
  and datasets in memory, runs training, and owns the alert feed.
- **realtime** — the only process that keeps sockets open for minutes or hours. Small import graph
  (no SQLAlchemy, no pandas) because every byte of a long-lived connection process counts.

They communicate only through network contracts (gRPC and loopback HTTP), authenticate each other with
`INTERNAL_TOKEN`, and are started, restarted and logged independently by supervisord. Moving one to its
own container means changing `ENGINE_GRPC_ADDRESS` or `REALTIME_INTERNAL_URL`, nothing else.

```
edge (Caddy)  ──/ws, /realtime/*──►  realtime  ──gRPC──►  engine  ──SQL──►  PostgreSQL
     └────────────── everything else ─►  gateway  ──gRPC──┘    ▲
                                          │   └────── SQL ─────┘
                                          └── HTTP (loopback) ──► realtime  /internal/events
```

## The gRPC contract (`proto/volcano/engine/v1/engine.proto`)

| RPC | Type | Client | Browser transport |
|---|---|---|---|
| `GetStatus`, `Predict`, `RefreshForecasts`, `StartTraining`, `GetTrainingStatus` | unary | gateway | JSON |
| `Train` | server streaming | gateway | Server-Sent Events (`POST /engine/training`) |
| `WatchAlerts` | server streaming | realtime | WebSocket fan-out |
| `UploadPharmacyReports` | client streaming | gateway | `POST /engine/pharmacy-upload` |
| `SimulateScenarios` | bidirectional | realtime | WebSocket conversation |

Conventions: package versioned (`v1`); enum values prefixed with their type (`RISK_LEVEL_RED`) and mapped
to the bare domain names in `volcano/rpc/conversion.py`; domain errors become gRPC status codes on the
server and HTTP status codes on the clients (`volcano/rpc/errors.py`). Interceptors add the token check
and per-RPC logging (method, status, duration, messages streamed). Standard health checking and server
reflection are enabled (`grpcurl -plaintext 127.0.0.1:50051 list`).

## The WebSocket protocol (`WS /ws`)

One socket per page multiplexes every live feature; messages are JSON objects with a `type`.

```
client → server   subscribe {channel: "alerts", municipality_id?} · unsubscribe · simulate {scenario} · ping
server → client   welcome · alerts.snapshot · alert {event} · simulation.result · presence · system ·
                  upstream {status} · ping · pong · error {code, message}
```

- **Fan-out instead of one stream per tab.** The hub keeps exactly one `WatchAlerts` stream to the engine
  and mirrors the active alerts, so a new subscriber gets a snapshot without touching the engine.
- **Demand-driven upstream.** That one stream only exists while at least one browser is subscribed; it
  closes a minute after the last one leaves. With nobody watching the engine does not poll the database,
  so an idle deployment lets a serverless PostgreSQL scale to zero.
- **Reconnection without gaps.** If the engine restarts, the relay reconnects with exponential back-off
  plus jitter. The engine replays the active alerts followed by a `SYNCED` marker; the relay diffs the
  replay against what it had and announces what was created or closed while it was disconnected.
- **Back-pressure.** Every client has a bounded outbound queue drained by its own sender task. Broadcasting
  never awaits a socket; a client that cannot keep up is closed with code 1013 and reconnects.
- **Security.** Browsers do not apply CORS to WebSockets, so the hub checks the `Origin` header against
  `CORS_ORIGINS`/`CORS_ORIGIN_REGEX`. Messages are validated with a discriminated union and capped at 8 KB.
  `/internal/events` requires the internal token and is not routed by the edge proxy at all.
- **Liveness.** An application-level `ping` every 25 s keeps idle sockets open through proxies and lets
  the browser notice a dead connection quickly.
- **Keep-awake.** On hosts that sleep without inbound traffic, the hub requests the service's own public
  `/live` at a fixed interval (see `docs/deployment.md`).

System events (`data.updated`, `model.trained`) are published by the gateway's daily job and the engine's
training runs, so open dashboards can refresh themselves.

## Memory budget (measured locally with `MALLOC_ARENA_MAX=2`)

| Process | RSS |
|---|---|
| engine (4 models loaded) | ~240 MB |
| gateway | ~95-125 MB |
| realtime | ~60-70 MB |
| supervisord | ~25 MB |
| Caddy | ~25 MB |

About 450-490 MB in steady state against Render's 512 MB. The engine grows while training; if it were
killed, supervisord restarts only that process, the gateway answers 503 for engine endpoints meanwhile and
the hub reconnects by itself. Lower `ENGINE_GRPC_THREADS` or `ENGINE_CACHE_TTL_S` to trade latency for
memory.

## Database migration to English names (0004)

`alembic/versions/0004_english_schema.py` creates the English tables, copies every row (translating enum
values and the JSON documents of models and predictions), drops the Spanish tables and moves PostgreSQL
sequences past the copied ids. Model artifacts are not copied — they were pickled with the old module
paths — so the engine retrains on start-up while the dashboard keeps showing the stored predictions.
It was tested on SQLite and PostgreSQL 16 with a database seeded by the previous version.
