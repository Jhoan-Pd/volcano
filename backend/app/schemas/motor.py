"""Esquemas REST del puente hacia el motor gRPC (lo que ve el navegador)."""
from pydantic import BaseModel, Field

from app.schemas.dashboard import Umbrales


class EstadoMotorOut(BaseModel):
    disponible: bool
    version: str | None = None
    modelos_en_memoria: int = 0
    entrenando: bool = False
    activo_desde_s: float | None = None
    rpcs_atendidas: int = 0
    latencia_ms: float | None = Field(None, description="Ida y vuelta API → motor → API")
    mensaje: str | None = None


class PuntoMotor(BaseModel):
    anio: int
    semana_epi: int
    etiqueta: str
    horizonte: int
    casos_esperados: float
    limite_inferior: float
    limite_superior: float
    nivel: str | None
    umbrales: Umbrales | None = None


class PronosticoMotor(BaseModel):
    municipio_id: int
    municipio: str
    enfermedad_id: int
    enfermedad: str
    algoritmo: str
    modelo_id: int
    semana_base: str
    nivel_max: str | None
    puntos: list[PuntoMotor]
    duracion_ms: float = Field(description="Tiempo de cálculo dentro del motor")
    desde_cache: bool = Field(description="El modelo ya estaba cargado en memoria")


class ProgresoOut(BaseModel):
    etapa: str
    mensaje: str
    porcentaje: float
    enfermedad: str | None = None
    algoritmo: str | None = None
    mae: float | None = None
    mae_base: float | None = None


class AlertaMotor(BaseModel):
    id: int
    municipio_id: int
    municipio: str
    enfermedad_id: int
    enfermedad: str
    semana: str
    nivel: str | None
    origen: str
    mensaje: str


class EventoAlertaOut(BaseModel):
    tipo: str = Field(description="ACTIVA | NUEVA | ACTUALIZADA | CERRADA")
    momento: str
    alerta: AlertaMotor


class FilaCargaIn(BaseModel):
    """Una fila del CSV ya leída y revisada en el navegador por el Web Worker."""
    fila: int = Field(ge=1)
    farmacia_id: int | None = None
    anio: int = Field(ge=2015, le=2100)
    semana_epi: int = Field(ge=1, le=53)
    categoria: str = Field(min_length=1, max_length=40)
    unidades: int = Field(ge=0, le=1_000_000)


class CargaFarmaciaIn(BaseModel):
    filas: list[FilaCargaIn] = Field(min_length=1, max_length=20_000)


class ErrorFilaOut(BaseModel):
    fila: int
    mensaje: str


class ResumenCargaOut(BaseModel):
    filas_recibidas: int
    filas_rechazadas: int
    semanas_creadas: int
    semanas_actualizadas: int
    semanas_rechazadas: int
    errores: list[ErrorFilaOut]
    duracion_ms: float


class EscenarioIn(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    municipio_id: int
    enfermedad_id: int
    delta_temperatura_c: float = 0
    cambio_lluvia_pct: float = 0
    cambio_busquedas_pct: float = 0
    cambio_farmacias_pct: float = 0
    ceniza: bool = False


class ResultadoEscenarioOut(BaseModel):
    id: str
    municipio_id: int
    enfermedad_id: int
    base: list[PuntoMotor]
    escenario: list[PuntoMotor]
    nivel_max: str | None
    variacion_pct: float
    resumen: str
    duracion_ms: float
    error: str | None = None
