from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.comun import ORMModel


class ClimaDiario(ORMModel):
    fecha: date
    temp_max_c: float | None
    temp_min_c: float | None
    temp_media_c: float | None
    precipitacion_mm: float | None
    humedad_relativa_pct: float | None
    es_pronostico: bool
    es_simulado: bool
    fuente: str


class ClimaActual(BaseModel):
    municipio_id: int
    municipio: str
    hora: datetime | None
    temperatura_c: float | None
    humedad_relativa_pct: float | None
    precipitacion_mm: float | None
    viento_kmh: float | None
    codigo_tiempo: int | None
    descripcion: str
    fuente: str  # "open-meteo" (en vivo) o "bd" (último registro guardado)


class ClimaSemanal(BaseModel):
    anio: int
    semana_epi: int
    etiqueta: str
    temp_media_c: float | None
    precipitacion_mm: float | None
    humedad_relativa_pct: float | None


class ResultadoSincronizacion(BaseModel):
    municipios: int
    registros_guardados: int
    errores: list[str]
