"""Esquemas de municipios, enfermedades, farmacias y eventos volcánicos."""
from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from app.models.enums import NivelVolcanico, TipoEventoVolcanico
from app.schemas.comun import ORMModel

# ── Municipios ────────────────────────────────────────────────────────────────


class MunicipioBase(BaseModel):
    codigo_divipola: str = Field(pattern=r"^\d{5}$", description="Código DIVIPOLA de 5 dígitos")
    nombre: str = Field(min_length=2, max_length=80)
    departamento: str = Field(default="Nariño", max_length=60)
    latitud: float = Field(ge=-4.5, le=13.5, description="Latitud dentro de Colombia")
    longitud: float = Field(ge=-82, le=-66)
    altitud_m: int | None = Field(default=None, ge=0, le=6000)
    poblacion: int = Field(gt=0)
    distancia_crater_km: float | None = Field(default=None, ge=0)
    activo: bool = True


class MunicipioCreate(MunicipioBase):
    pass


class MunicipioUpdate(BaseModel):
    codigo_divipola: str | None = Field(default=None, pattern=r"^\d{5}$")
    nombre: str | None = Field(default=None, min_length=2, max_length=80)
    departamento: str | None = None
    latitud: float | None = Field(default=None, ge=-4.5, le=13.5)
    longitud: float | None = Field(default=None, ge=-82, le=-66)
    altitud_m: int | None = Field(default=None, ge=0, le=6000)
    poblacion: int | None = Field(default=None, gt=0)
    distancia_crater_km: float | None = Field(default=None, ge=0)
    activo: bool | None = None


class MunicipioOut(ORMModel, MunicipioBase):
    id: int


# ── Enfermedades ──────────────────────────────────────────────────────────────


class _UmbralesMixin(BaseModel):
    @model_validator(mode="after")
    def _orden_umbrales(self):
        a, n, r = self.umbral_amarillo_pct, self.umbral_naranja_pct, self.umbral_rojo_pct
        if None not in (a, n, r) and not (a < n < r):
            raise ValueError("Los umbrales deben cumplir amarillo < naranja < rojo")
        return self


class EnfermedadBase(_UmbralesMixin):
    codigo: str = Field(pattern=r"^[A-Z0-9_]{2,20}$", description="Ej.: IRA, EDA, DENGUE")
    nombre: str = Field(min_length=2, max_length=100)
    descripcion: str | None = None
    codigo_cie10: str | None = Field(default=None, max_length=40)
    recomendaciones: str | None = None
    terminos_busqueda: str | None = Field(default=None, max_length=300)
    color: str = Field(default="#2a78d6", pattern=r"^#[0-9a-fA-F]{6}$")
    umbral_amarillo_pct: int = Field(default=50, ge=1, le=99)
    umbral_naranja_pct: int = Field(default=75, ge=1, le=99)
    umbral_rojo_pct: int = Field(default=90, ge=1, le=99)
    activo: bool = True


class EnfermedadCreate(EnfermedadBase):
    pass


class EnfermedadUpdate(_UmbralesMixin):
    codigo: str | None = Field(default=None, pattern=r"^[A-Z0-9_]{2,20}$")
    nombre: str | None = Field(default=None, min_length=2, max_length=100)
    descripcion: str | None = None
    codigo_cie10: str | None = None
    recomendaciones: str | None = None
    terminos_busqueda: str | None = None
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    umbral_amarillo_pct: int | None = Field(default=None, ge=1, le=99)
    umbral_naranja_pct: int | None = Field(default=None, ge=1, le=99)
    umbral_rojo_pct: int | None = Field(default=None, ge=1, le=99)
    activo: bool | None = None


class EnfermedadOut(ORMModel, EnfermedadBase):
    id: int


# ── Farmacias ─────────────────────────────────────────────────────────────────


class FarmaciaBase(BaseModel):
    nombre: str = Field(min_length=3, max_length=120)
    nit: str = Field(pattern=r"^\d{6,12}(-\d)?$", description="NIT, ej. 900123456-7")
    direccion: str | None = Field(default=None, max_length=200)
    telefono: str | None = Field(default=None, pattern=r"^[0-9 +()-]{7,20}$")
    municipio_id: int
    usuario_id: int | None = None
    latitud: float | None = Field(default=None, ge=-4.5, le=13.5)
    longitud: float | None = Field(default=None, ge=-82, le=-66)
    activa: bool = True


class FarmaciaCreate(FarmaciaBase):
    pass


class FarmaciaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=3, max_length=120)
    nit: str | None = Field(default=None, pattern=r"^\d{6,12}(-\d)?$")
    direccion: str | None = None
    telefono: str | None = Field(default=None, pattern=r"^[0-9 +()-]{7,20}$")
    municipio_id: int | None = None
    usuario_id: int | None = None
    latitud: float | None = None
    longitud: float | None = None
    activa: bool | None = None


class FarmaciaOut(ORMModel, FarmaciaBase):
    id: int


# ── Eventos volcánicos ────────────────────────────────────────────────────────


class _FechasMixin(BaseModel):
    @model_validator(mode="after")
    def _coherencia(self):
        if self.fecha_inicio and self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            raise ValueError("fecha_fin no puede ser anterior a fecha_inicio")
        if getattr(self, "tipo", None) == TipoEventoVolcanico.CAIDA_CENIZA:
            if not self.municipio_id:
                raise ValueError("Una caída de ceniza debe indicar el municipio afectado")
            if not self.intensidad_ceniza:
                raise ValueError("Una caída de ceniza debe tener intensidad entre 1 y 3")
        return self


class EventoVolcanicoBase(_FechasMixin):
    tipo: TipoEventoVolcanico
    nivel_actividad: NivelVolcanico
    fecha_inicio: date
    fecha_fin: date | None = None
    municipio_id: int | None = None
    intensidad_ceniza: int = Field(default=0, ge=0, le=3, description="0 ninguna, 1 leve, 2 moderada, 3 fuerte")
    so2_ton_dia: float | None = Field(default=None, ge=0)
    descripcion: str | None = None
    url_boletin: str | None = Field(default=None, max_length=400)


class EventoVolcanicoCreate(EventoVolcanicoBase):
    pass


class EventoVolcanicoUpdate(_FechasMixin):
    tipo: TipoEventoVolcanico | None = None
    nivel_actividad: NivelVolcanico | None = None
    fecha_inicio: date | None = None
    fecha_fin: date | None = None
    municipio_id: int | None = None
    intensidad_ceniza: int | None = Field(default=None, ge=0, le=3)
    so2_ton_dia: float | None = Field(default=None, ge=0)
    descripcion: str | None = None
    url_boletin: str | None = None


class EventoVolcanicoOut(ORMModel, EventoVolcanicoBase):
    id: int
    es_simulado: bool
    creado_en: datetime

    # La salida no re-valida reglas de negocio (los datos ya están guardados)
    @model_validator(mode="after")
    def _coherencia(self):
        return self
