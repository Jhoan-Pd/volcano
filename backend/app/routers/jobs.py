"""Tareas programadas. GitHub Actions llama este endpoint una vez al día (Fase 3)."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import verificar_cron
from app.db.session import get_db
from app.services.clima_service import ClimaService

router = APIRouter(prefix="/jobs", tags=["Tareas programadas"], dependencies=[Depends(verificar_cron)])


@router.post("/actualizar-datos", summary="Actualiza fuentes externas (requiere cabecera X-Cron-Secret)")
def actualizar_datos(db: Session = Depends(get_db)):
    inicio = datetime.now(timezone.utc)
    clima = ClimaService(db).sincronizar(dias_pasados=14)
    # Fase 2: + TrendsFuente, SivigilaFuente y reentrenamiento del modelo
    return {
        "inicio": inicio.isoformat(),
        "fin": datetime.now(timezone.utc).isoformat(),
        "clima": clima.model_dump(),
    }
