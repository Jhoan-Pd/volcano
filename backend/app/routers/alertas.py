"""Alertas tempranas: las activas son públicas (banner); la gestión es del ADMIN."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import solo_admin
from app.db.session import get_db
from app.schemas.alerta import AlertaOut, ResultadoEvaluacion
from app.schemas.comun import Pagina
from app.services.alerta_service import AlertaService

router = APIRouter(prefix="/alertas", tags=["Alertas"])


@router.get("/activas", response_model=list[AlertaOut], summary="Alertas vigentes (riesgo alto o muy alto)")
def activas(db: Session = Depends(get_db)):
    return AlertaService(db).activas()


@router.get("", response_model=Pagina[AlertaOut], dependencies=[Depends(solo_admin)],
            summary="Historial de alertas — solo ADMIN")
def listar(activa: bool | None = Query(None), offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=200),
           db: Session = Depends(get_db)):
    return AlertaService(db).listar(activa, offset, limit)


@router.post("/evaluar", response_model=ResultadoEvaluacion, dependencies=[Depends(solo_admin)],
             summary="Recalcular alertas ahora y enviar correos pendientes — solo ADMIN")
def evaluar(enviar_correo: bool = Query(True), db: Session = Depends(get_db)):
    return AlertaService(db).evaluar(enviar_correo=enviar_correo)


@router.patch("/{alerta_id}/cerrar", response_model=AlertaOut, dependencies=[Depends(solo_admin)],
              summary="Cerrar una alerta (no se reabre salvo que el riesgo empeore) — solo ADMIN")
def cerrar(alerta_id: int, db: Session = Depends(get_db)):
    return AlertaService(db).cerrar(alerta_id)
