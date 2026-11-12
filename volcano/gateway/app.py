"""Gateway microservice: the public REST API.

    Local:    uvicorn volcano.gateway.app:app --reload --port 8001
    Swagger:  http://localhost:8001/docs

Behind the edge proxy it serves everything except `/ws` and `/realtime/*` (realtime hub). It owns
HTTP concerns — authentication, validation, CRUD, dashboard reads, reports, CSV uploads, the daily
job — and delegates every ML operation to the engine over gRPC.
"""
import asyncio
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from volcano import __version__
from volcano.db.session import engine as db_engine
from volcano.gateway.errors import register_error_handlers
from volcano.gateway.routers import (
    alerts,
    auth,
    catalog,
    dashboard,
    data_sources,
    jobs,
    model,
    pharmacy,
    reports,
    users,
    weather,
)
from volcano.gateway.routers import engine as engine_router
from volcano.rpc.client import EngineClient, engine_client
from volcano.shared.config import settings
from volcano.shared.log_config import configure_logging

logger = logging.getLogger("volcano.gateway")

DESCRIPTION = """
REST API of the **Disease Outbreak Predictor** for Pasto and the Galeras volcano area (Nariño, Colombia).

It combines weather (Open-Meteo), symptom searches (Google Trends), pharmacy reports, official cases
(SIVIGILA) and volcanic activity to raise early alerts. Live alerts and the scenario simulator are
served over WebSocket by the realtime service at `/ws`.

**Authentication:** use *Authorize* with a seed user. Roles: `ADMIN`, `PHARMACY`, `CITIZEN`.
The dashboard endpoints are public. User-facing messages are in Spanish.
"""


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging("gateway")
    yield
    await engine_client().close()


app = FastAPI(
    title=settings.APP_NAME,
    version=__version__,
    description=DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],  # the frontend reads the report file name
)

register_error_handlers(app)

for r in (auth.router, users.router, catalog.municipalities, catalog.diseases, catalog.pharmacies,
          catalog.volcanic_events, weather.router, dashboard.router, data_sources.router, pharmacy.router,
          model.router, engine_router.router, alerts.router, reports.router, jobs.router):
    app.include_router(r, prefix=settings.API_PREFIX)


@app.get("/", tags=["Health"], summary="Basic information")
def root():
    return {"app": settings.APP_NAME, "version": app.version, "docs": "/docs"}


@app.get("/live", tags=["Health"], summary="Liveness: the process answers (touches nothing else)")
def live():
    """What the platform's health check and the keep-awake ping call, every few seconds or minutes.
    It must not query the database: a serverless PostgreSQL would never be allowed to scale to zero."""
    return {"status": "ok"}


@app.get("/health", tags=["Health"], summary="Readiness: the API can reach the database")
def health():
    with db_engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}


async def _realtime_status() -> dict:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"{settings.REALTIME_INTERNAL_URL.rstrip('/')}/realtime/health")
            r.raise_for_status()
            return {"available": True, **r.json()}
    except (httpx.HTTPError, ValueError) as exc:
        return {"available": False, "message": str(exc)}


@app.get("/health/services", tags=["Health"], summary="Status of the three microservices")
async def services_health(engine: EngineClient = Depends(engine_client)):
    """Gateway, engine (gRPC health over a real RPC) and realtime hub, checked concurrently."""
    engine_status, realtime_status = await asyncio.gather(engine.status(), _realtime_status())
    return {"gateway": {"available": True, "version": app.version},
            "engine": engine_status.model_dump(), "realtime": realtime_status}
