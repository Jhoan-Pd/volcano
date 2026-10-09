"""Endpoints públicos del dashboard (no requieren login)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.dashboard import EstadoVolcan, ResumenDashboard, RiesgoMunicipio, SerieEnfermedad
from app.schemas.modelo import ExplicacionPrediccion, PrediccionEnfermedad
from app.services.dashboard_service import DashboardService
from app.services.prediccion_service import PrediccionService

router = APIRouter(prefix="/dashboard", tags=["Dashboard público"])


@router.get("/resumen", response_model=ResumenDashboard, summary="Semáforo por enfermedad + estado del volcán")
def resumen(municipio_id: int | None = Query(None, description="Por defecto, el primer municipio (Pasto)"),
            db: Session = Depends(get_db)):
    return DashboardService(db).resumen(municipio_id)


@router.get("/serie", response_model=SerieEnfermedad, summary="Serie semanal con canal endémico")
def serie(municipio_id: int, enfermedad_id: int, semanas: int = Query(104, ge=8, le=520),
          db: Session = Depends(get_db)):
    return DashboardService(db).serie(municipio_id, enfermedad_id, semanas)


@router.get("/riesgo-municipios", response_model=list[RiesgoMunicipio], summary="Nivel de riesgo de cada municipio")
def riesgo_municipios(db: Session = Depends(get_db)):
    return DashboardService(db).riesgo_por_municipio()


@router.get("/volcan", response_model=EstadoVolcan, summary="Estado actual del Volcán Galeras")
def volcan(db: Session = Depends(get_db)):
    return DashboardService(db).estado_volcan()


@router.get("/prediccion", response_model=PrediccionEnfermedad,
            summary="Casos esperados de las próximas 4 semanas con intervalo del 80 % y nivel de riesgo")
def prediccion(municipio_id: int, enfermedad_id: int, db: Session = Depends(get_db)):
    return PrediccionService(db).prediccion(municipio_id, enfermedad_id)


@router.get("/explicacion", response_model=ExplicacionPrediccion, summary="¿Por qué subió el riesgo? (explicabilidad)")
def explicacion(municipio_id: int, enfermedad_id: int, horizonte: int | None = Query(None, ge=1, le=4),
                db: Session = Depends(get_db)):
    return PrediccionService(db).explicacion(municipio_id, enfermedad_id, horizonte)
