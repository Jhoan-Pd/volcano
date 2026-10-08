"""Punto de entrada de la API.

Local:      uvicorn app.main:app --reload
Swagger:    http://localhost:8000/docs
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.core.errors import registrar_manejadores
from app.db.session import engine
from app.routers import auth, catalogos, clima, dashboard, datos, farmacia, jobs, usuarios

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

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
    version="1.0.0-fase1",
    description=DESCRIPCION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

registrar_manejadores(app)

for r in (auth.router, usuarios.router, catalogos.municipios, catalogos.enfermedades, catalogos.farmacias,
          catalogos.eventos_volcanicos, clima.router, dashboard.router, datos.router, farmacia.router,
          jobs.router):
    app.include_router(r, prefix=settings.API_PREFIX)


@app.get("/", tags=["Salud"], summary="Información básica")
def raiz():
    return {"app": settings.APP_NAME, "version": app.version, "docs": "/docs"}


@app.get("/health", tags=["Salud"], summary="Chequeo de salud (usado por Render)")
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok", "bd": "ok"}
