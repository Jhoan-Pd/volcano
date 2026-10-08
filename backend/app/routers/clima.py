from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import solo_admin
from app.db.session import get_db
from app.schemas.clima import ClimaActual, ClimaDiario, ClimaSemanal, ResultadoSincronizacion
from app.services.clima_service import ClimaService

router = APIRouter(prefix="/clima", tags=["Clima (Open-Meteo)"])


@router.get("/{municipio_id}/actual", response_model=ClimaActual, summary="Clima actual (en vivo, con caché)")
def actual(municipio_id: int, db: Session = Depends(get_db)):
    return ClimaService(db).actual(municipio_id)


@router.get("/{municipio_id}/pronostico", response_model=list[ClimaDiario], summary="Pronóstico diario (hasta 16 días)")
def pronostico(municipio_id: int, dias: int = Query(16, ge=1, le=16), db: Session = Depends(get_db)):
    return ClimaService(db).pronostico(municipio_id, dias)


@router.get("/{municipio_id}/semanal", response_model=list[ClimaSemanal], summary="Clima observado por semana epidemiológica")
def semanal(municipio_id: int, semanas: int = Query(52, ge=1, le=520), db: Session = Depends(get_db)):
    return ClimaService(db).semanal(municipio_id, semanas)


@router.post("/sincronizar", response_model=ResultadoSincronizacion, dependencies=[Depends(solo_admin)],
             summary="Descargar pronóstico y últimos días de Open-Meteo — solo ADMIN")
def sincronizar(dias_pasados: int = Query(14, ge=0, le=92), db: Session = Depends(get_db)):
    return ClimaService(db).sincronizar(dias_pasados)
