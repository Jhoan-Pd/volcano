"""Modelo predictivo: reentrenamiento (ADMIN), estado, historial y métricas."""
from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import solo_admin
from app.db.session import get_db
from app.schemas.modelo import EstadoEntrenamiento, ModeloOut
from app.services.entrenamiento import control
from app.services.entrenamiento import reentrenar as tarea_reentrenar
from app.services.prediccion_service import PrediccionService

router = APIRouter(prefix="/modelo", tags=["Modelo predictivo"])


@router.post("/reentrenar", response_model=EstadoEntrenamiento, status_code=status.HTTP_202_ACCEPTED,
             dependencies=[Depends(solo_admin)], summary="Reentrenar los modelos (en segundo plano) — solo ADMIN")
def reentrenar(tareas: BackgroundTasks, enfermedad_id: int | None = Query(None, description="Vacío = todas")):
    """Compara promedio móvil, Random Forest y Gradient Boosting; guarda el mejor con sus métricas
    y regenera las predicciones. Consulta el avance en `GET /modelo/estado`."""
    estado = control.iniciar()
    tareas.add_task(tarea_reentrenar, enfermedad_id)
    return estado


@router.get("/estado", response_model=EstadoEntrenamiento, dependencies=[Depends(solo_admin)],
            summary="Estado del último reentrenamiento")
def estado():
    return control.estado()


@router.post("/predecir", dependencies=[Depends(solo_admin)], summary="Regenerar predicciones con los modelos activos")
def predecir(db: Session = Depends(get_db)):
    return {"predicciones": PrediccionService(db).predecir()}


@router.get("/historial", response_model=list[ModeloOut], summary="Modelos entrenados con fecha y métricas (público)")
def historial(enfermedad_id: int | None = Query(None), limite: int = Query(50, ge=1, le=500),
              db: Session = Depends(get_db)):
    return PrediccionService(db).historial(enfermedad_id, limite)
