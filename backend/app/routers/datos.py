"""Fuentes de datos: sincronización manual (ADMIN) y consulta pública de las series."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import solo_admin
from app.db.session import get_db
from app.schemas.datos import ResultadoTendencias, SerieTendencia
from app.services.tendencia_service import TendenciaService

router = APIRouter(prefix="/datos", tags=["Fuentes de datos"])


@router.post("/sincronizar/tendencias", response_model=ResultadoTendencias, dependencies=[Depends(solo_admin)],
             summary="Descargar búsquedas de Google Trends (caché en BD, respaldo CSV) — solo ADMIN")
def sincronizar_tendencias(forzar: bool = Query(False, description="Ignorar la caché y volver a consultar"),
                           db: Session = Depends(get_db)):
    return TendenciaService(db).sincronizar(forzar=forzar)


@router.get("/tendencias", response_model=SerieTendencia, summary="Serie semanal de búsquedas de un término")
def tendencias(termino: str = Query(..., min_length=2, max_length=60), semanas: int = Query(104, ge=4, le=520),
               db: Session = Depends(get_db)):
    return TendenciaService(db).serie(termino, semanas)
