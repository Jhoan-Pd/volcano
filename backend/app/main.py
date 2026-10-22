"""Punto de entrada de la API.

Local:      uvicorn app.main:app --reload
Swagger:    http://localhost:8000/docs
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text

from app.core.config import settings
from app.core.errors import registrar_manejadores
from app.db.session import SessionLocal, engine
from app.models import CasoOficial, ModeloEntrenado
from app.routers import alertas, auth, catalogos, clima, dashboard, datos, farmacia, jobs, modelo, reportes, usuarios
from app.services.entrenamiento import lanzar_en_hilo

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("predictor")


def _entrenar_si_falta() -> None:
    """Primer arranque en la nube: entrena en un hilo para no retrasar la apertura del puerto."""
    try:
        with SessionLocal() as db:
            hay_modelos = (db.scalar(select(func.count()).select_from(ModeloEntrenado)) or 0) > 0
            hay_casos = (db.scalar(select(func.count()).select_from(CasoOficial)) or 0) > 0
        if hay_casos and not hay_modelos:
            lanzar_en_hilo(nombre="entrenamiento-inicial")
            logger.info("Sin modelos entrenados: entrenamiento inicial en segundo plano")
    except Exception as exc:  # noqa: BLE001 - nunca impedir que la API arranque
        logger.warning("No se pudo lanzar el entrenamiento inicial: %s", exc)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.ENTRENAR_AL_INICIO:
        _entrenar_si_falta()
    yield

DESCRIPCION = """
API del **Predictor de Brotes de Enfermedades** para Pasto y la zona de influencia del
Volcán Galeras (Nariño, Colombia).

Cruza clima (Open-Meteo), búsquedas de síntomas (Google Trends), reportes de farmacias,
casos oficiales (SIVIGILA) y actividad volcánica para emitir alertas tempranas.

**Autenticación:** usa el botón *Authorize* con un usuario del seed.
Roles: `ADMIN`, `FARMACIA`, `CIUDADANO`. Los endpoints del dashboard son públicos.
"""

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description=DESCRIPCION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],  # el frontend lee el nombre del archivo de los reportes
)

registrar_manejadores(app)

for r in (auth.router, usuarios.router, catalogos.municipios, catalogos.enfermedades, catalogos.farmacias,
          catalogos.eventos_volcanicos, clima.router, dashboard.router, datos.router, farmacia.router,
          modelo.router, alertas.router, reportes.router, jobs.router):
    app.include_router(r, prefix=settings.API_PREFIX)


@app.get("/", tags=["Salud"], summary="Información básica")
def raiz():
    return {"app": settings.APP_NAME, "version": app.version, "docs": "/docs"}


@app.get("/health", tags=["Salud"], summary="Chequeo de salud (usado por Render)")
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok", "bd": "ok"}
