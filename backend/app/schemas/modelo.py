"""Esquemas del modelo predictivo: métricas, predicciones y explicaciones."""
from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.dashboard import ResumenPrediccion, Umbrales  # noqa: F401 (se reexporta)


class ModeloOut(BaseModel):
    id: int
    enfermedad_id: int
    enfermedad: str
    algoritmo: str
    version: str
    fecha_entrenamiento: datetime
    mae_base: float | None
    rmse_base: float | None
    mae_modelo: float | None
    rmse_modelo: float | None
    mejora_mae_pct: float | None
    n_muestras: int | None
    activo: bool
    importancias: dict | None
    metricas: dict | None


class EstadoEntrenamiento(BaseModel):
    en_curso: bool
    inicio: datetime | None = None
    fin: datetime | None = None
    mensaje: str | None = None
    errores: list[str] = []


class ModeloResumen(BaseModel):
    id: int
    algoritmo: str
    fecha_entrenamiento: datetime
    mae_base: float | None
    mae_modelo: float | None
    rmse_base: float | None
    rmse_modelo: float | None


class PuntoPrediccion(BaseModel):
    anio: int
    semana_epi: int
    etiqueta: str
    fecha_inicio: date
    horizonte: int
    casos_esperados: float
    limite_inferior: float
    limite_superior: float
    nivel: str
    umbrales: Umbrales | None


class PuntoBacktest(BaseModel):
    anio: int
    semana_epi: int
    etiqueta: str
    real: float
    predicho: float


class PrediccionEnfermedad(BaseModel):
    municipio_id: int
    enfermedad_id: int
    enfermedad: str
    semana_base: str | None
    modelo: ModeloResumen | None
    nivel_max: str | None
    puntos: list[PuntoPrediccion]
    backtest: list[PuntoBacktest]


class FactorExplicacion(BaseModel):
    grupo: str
    contribucion: float  # casos que aporta el grupo frente a su valor típico
    direccion: str  # sube | baja | neutral
    mensaje: str | None


class ExplicacionPrediccion(BaseModel):
    municipio_id: int
    municipio: str
    enfermedad_id: int
    enfermedad: str
    etiqueta: str
    horizonte: int
    nivel: str
    casos_esperados: float
    metodo: str
    resumen: str
    factores: list[FactorExplicacion]
    importancia_global: dict | None
