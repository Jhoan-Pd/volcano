"""Esquemas de sincronización e importación de fuentes de datos."""
from datetime import date

from pydantic import BaseModel


class ResultadoTendencias(BaseModel):
    fuente: str  # pytrends | csv | cache
    terminos: list[str]
    registros_guardados: int
    desde_cache: list[str]
    errores: list[str]


class PuntoTendencia(BaseModel):
    anio: int
    semana_epi: int
    etiqueta: str
    fecha_semana: date
    indice: float
    fuente: str
    es_simulado: bool


class SerieTendencia(BaseModel):
    termino: str
    region: str
    puntos: list[PuntoTendencia]


class ResultadoSivigila(BaseModel):
    enfermedades: list[str]
    anios_cubiertos: list[int]
    registros_guardados: int
    semanas_con_casos: int
    errores: list[str]


class ErrorFila(BaseModel):
    fila: int
    mensaje: str


class ResultadoImportacion(BaseModel):
    tipo: str
    filas_leidas: int
    insertadas: int
    actualizadas: int
    errores: list[ErrorFila]


class EstadoFuente(BaseModel):
    fuente: str
    tabla: str
    registros: int
    simulados: int
    ultima_semana: str | None
    ultima_actualizacion: str | None


class EstadoDatos(BaseModel):
    fuentes: list[EstadoFuente]
