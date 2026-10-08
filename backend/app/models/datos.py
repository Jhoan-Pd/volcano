"""Tablas de datos de entrada del modelo (series de tiempo)."""
from datetime import date

from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class RegistroClima(TimestampMixin, Base):
    """Clima diario por municipio (histórico y pronóstico de Open-Meteo)."""
    __tablename__ = "registros_clima"
    __table_args__ = (UniqueConstraint("municipio_id", "fecha"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    municipio_id: Mapped[int] = mapped_column(ForeignKey("municipios.id", ondelete="CASCADE"), index=True, nullable=False)
    fecha: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    temp_max_c: Mapped[float | None] = mapped_column(Float)
    temp_min_c: Mapped[float | None] = mapped_column(Float)
    temp_media_c: Mapped[float | None] = mapped_column(Float)
    precipitacion_mm: Mapped[float | None] = mapped_column(Float)
    humedad_relativa_pct: Mapped[float | None] = mapped_column(Float)
    es_pronostico: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    es_simulado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fuente: Mapped[str] = mapped_column(String(40), default="open-meteo", nullable=False)


class TendenciaBusqueda(TimestampMixin, Base):
    """Índice semanal (0-100) de Google Trends por término y región."""
    __tablename__ = "tendencias_busqueda"
    __table_args__ = (UniqueConstraint("termino", "region", "anio", "semana_epi"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    termino: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    region: Mapped[str] = mapped_column(String(10), default="CO-NAR", nullable=False)
    anio: Mapped[int] = mapped_column(Integer, nullable=False)
    semana_epi: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_semana: Mapped[date] = mapped_column(Date, nullable=False)
    indice: Mapped[float] = mapped_column(Float, nullable=False)
    fuente: Mapped[str] = mapped_column(String(20), default="pytrends", nullable=False)  # pytrends|csv|simulado
    es_simulado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class CasoOficial(TimestampMixin, Base):
    """Casos semanales notificados (SIVIGILA/INS) por municipio y enfermedad."""
    __tablename__ = "casos_oficiales"
    __table_args__ = (UniqueConstraint("municipio_id", "enfermedad_id", "anio", "semana_epi"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    municipio_id: Mapped[int] = mapped_column(ForeignKey("municipios.id", ondelete="CASCADE"), index=True, nullable=False)
    enfermedad_id: Mapped[int] = mapped_column(ForeignKey("enfermedades.id", ondelete="CASCADE"), index=True, nullable=False)
    anio: Mapped[int] = mapped_column(Integer, nullable=False)
    semana_epi: Mapped[int] = mapped_column(Integer, nullable=False)
    casos: Mapped[int] = mapped_column(Integer, nullable=False)
    fuente: Mapped[str] = mapped_column(String(40), default="SIVIGILA", nullable=False)
    es_simulado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class EventoVolcanico(TimestampMixin, Base):
    """Boletines de actividad del Galeras y eventos de caída de ceniza (registro del admin)."""
    __tablename__ = "eventos_volcanicos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)  # TipoEventoVolcanico
    nivel_actividad: Mapped[str] = mapped_column(String(10), nullable=False)  # NivelVolcanico
    fecha_inicio: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    fecha_fin: Mapped[date | None] = mapped_column(Date)
    municipio_id: Mapped[int | None] = mapped_column(ForeignKey("municipios.id", ondelete="SET NULL"), index=True)
    intensidad_ceniza: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 0 ninguna..3 fuerte
    so2_ton_dia: Mapped[float | None] = mapped_column(Float)
    descripcion: Mapped[str | None] = mapped_column(Text)
    url_boletin: Mapped[str | None] = mapped_column(String(400))
    es_simulado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    registrado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))

    municipio: Mapped["Municipio | None"] = relationship(lazy="joined")  # noqa: F821
