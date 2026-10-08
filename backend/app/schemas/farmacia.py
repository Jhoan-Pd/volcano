"""Esquemas del módulo de farmacias (reporte semanal de ventas)."""
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.epi import semanas_del_anio
from app.models.enums import CategoriaProducto

MAX_UNIDADES = 100_000


class ItemReporte(BaseModel):
    categoria: CategoriaProducto
    unidades: int = Field(ge=0, le=MAX_UNIDADES, description="Unidades vendidas en la semana")


class _ItemsMixin(BaseModel):
    items: list[ItemReporte] = Field(min_length=1, max_length=len(CategoriaProducto))

    @field_validator("items")
    @classmethod
    def _sin_repetidos(cls, items: list[ItemReporte]) -> list[ItemReporte]:
        cats = [i.categoria for i in items]
        repetidas = {c.value for c in cats if cats.count(c) > 1}
        if repetidas:
            raise ValueError(f"Categoría repetida: {', '.join(sorted(repetidas))}")
        return items


class ReporteSemanalIn(_ItemsMixin):
    anio: int = Field(ge=2015, le=2100)
    semana_epi: int = Field(ge=1, le=53)
    farmacia_id: int | None = Field(default=None, description="Solo ADMIN: farmacia por la que reporta")

    @model_validator(mode="after")
    def _semana_existe(self):
        if self.semana_epi > semanas_del_anio(self.anio):
            raise ValueError(f"El año {self.anio} solo tiene {semanas_del_anio(self.anio)} semanas epidemiológicas")
        return self


class ReporteSemanalUpdate(_ItemsMixin):
    pass


class ItemReporteOut(BaseModel):
    categoria: str
    unidades: int


class ReporteSemanalOut(BaseModel):
    farmacia_id: int
    farmacia: str
    anio: int
    semana_epi: int
    etiqueta: str
    fecha_inicio: date
    fecha_fin: date
    items: list[ItemReporteOut]
    total_unidades: int
    es_simulado: bool
    actualizado_en: datetime | None
    reportado_por: str | None
    editable: bool


class SemanaReportable(BaseModel):
    anio: int
    semana_epi: int
    etiqueta: str
    fecha_inicio: date
    fecha_fin: date
    reportada: bool


class MiFarmacia(BaseModel):
    id: int
    nombre: str
    nit: str
    direccion: str | None
    municipio_id: int
    municipio: str
    activa: bool
    semanas_reportables: list[SemanaReportable]
    categorias: list[str]


class IndiceFarmacia(BaseModel):
    anio: int
    semana_epi: int
    etiqueta: str
    categoria: str
    unidades: int
    farmacias_reportando: int
    indice: float | None  # 100 = promedio de las 52 semanas anteriores
