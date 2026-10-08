from datetime import date

from pydantic import BaseModel


class Umbrales(BaseModel):
    amarillo: float
    naranja: float
    rojo: float


class RiesgoEnfermedad(BaseModel):
    enfermedad_id: int
    codigo: str
    nombre: str
    color: str
    anio: int
    semana_epi: int
    casos: int
    casos_semana_anterior: int | None
    variacion_pct: float | None
    tasa_x_100k: float
    umbrales: Umbrales
    nivel: str  # VERDE | AMARILLO | NARANJA | ROJO
    es_simulado: bool
    recomendaciones: list[str]


class EstadoVolcan(BaseModel):
    nivel_actividad: str
    fecha: date | None
    descripcion: str | None
    url_boletin: str | None
    es_simulado: bool
    so2_ton_dia: float | None
    ceniza_reciente: list["EventoCeniza"]


class EventoCeniza(BaseModel):
    fecha: date
    municipio: str | None
    intensidad: int
    descripcion: str | None
    es_simulado: bool


class ResumenDashboard(BaseModel):
    municipio_id: int
    municipio: str
    poblacion: int
    semana_referencia: str
    riesgos: list[RiesgoEnfermedad]
    volcan: EstadoVolcan
    hay_datos_simulados: bool


class PuntoSerie(BaseModel):
    anio: int
    semana_epi: int
    etiqueta: str
    fecha_inicio: date
    casos: int | None
    p_amarillo: float | None
    p_naranja: float | None
    p_rojo: float | None


class SerieEnfermedad(BaseModel):
    municipio_id: int
    enfermedad_id: int
    enfermedad: str
    puntos: list[PuntoSerie]


class RiesgoMunicipio(BaseModel):
    municipio_id: int
    municipio: str
    codigo_divipola: str
    latitud: float
    longitud: float
    nivel_max: str
    detalle: dict[str, str]  # codigo enfermedad -> nivel


EstadoVolcan.model_rebuild()
