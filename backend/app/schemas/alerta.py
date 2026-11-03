"""Esquemas de alertas tempranas."""
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import NivelRiesgo, OrigenAlerta


class AlertaOut(BaseModel):
    id: int
    municipio_id: int
    municipio: str
    enfermedad_id: int
    enfermedad: str
    codigo_enfermedad: str
    anio: int
    semana_epi: int
    etiqueta: str
    nivel_riesgo: str  # NARANJA | ROJO
    origen: str  # OBSERVADO | PREDICHO
    mensaje: str
    activa: bool
    notificada_email: bool
    creado_en: datetime
    cerrada_en: datetime | None


class ResultadoEvaluacion(BaseModel):
    nuevas: int
    actualizadas: int
    cerradas: int
    activas: int
    correos_enviados: int


class FiltrosAlertas(BaseModel):
    q: str | None = Field(None, max_length=80, description="Texto en el mensaje, municipio o enfermedad")
    municipio_id: int | None = None
    enfermedad_id: int | None = None
    nivel: NivelRiesgo | None = None
    origen: OrigenAlerta | None = None
    activa: bool | None = None
