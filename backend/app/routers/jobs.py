"""Tareas programadas. GitHub Actions llama este endpoint una vez al día."""
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import verificar_cron
from app.db.session import get_db
from app.services.actualizacion_service import ActualizacionService

router = APIRouter(prefix="/jobs", tags=["Tareas programadas"], dependencies=[Depends(verificar_cron)])


@router.post("/actualizar-datos", summary="Actualización diaria de fuentes, predicciones y alertas (cabecera X-Cron-Secret)")
def actualizar_datos(
    sivigila: Literal["auto", "si", "no"] = Query("auto", description="auto = solo los lunes"),
    reentrenar: Literal["auto", "si", "no"] = Query("auto", description="auto = los lunes o si no hay modelos"),
    db: Session = Depends(get_db),
):
    """Clima → búsquedas → (SIVIGILA) → predicciones o reentrenamiento → alertas.
    Cada paso informa si terminó bien; uno fallido no detiene a los demás."""
    return ActualizacionService(db).ejecutar(sivigila=sivigila, reentrenar=reentrenar)
