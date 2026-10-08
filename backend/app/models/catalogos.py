from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Municipio(TimestampMixin, Base):
    __tablename__ = "municipios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo_divipola: Mapped[str] = mapped_column(String(5), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)
    departamento: Mapped[str] = mapped_column(String(60), default="Nariño", nullable=False)
    latitud: Mapped[float] = mapped_column(Float, nullable=False)
    longitud: Mapped[float] = mapped_column(Float, nullable=False)
    altitud_m: Mapped[int | None] = mapped_column(Integer)
    poblacion: Mapped[int] = mapped_column(Integer, nullable=False)
    distancia_crater_km: Mapped[float | None] = mapped_column(Float)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Enfermedad(TimestampMixin, Base):
    __tablename__ = "enfermedades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text)
    codigo_cie10: Mapped[str | None] = mapped_column(String(40))
    recomendaciones: Mapped[str | None] = mapped_column(Text)  # una recomendación por línea
    terminos_busqueda: Mapped[str | None] = mapped_column(String(300))  # separados por coma
    color: Mapped[str] = mapped_column(String(9), default="#2a78d6", nullable=False)
    # Umbrales del canal endémico (percentiles históricos de la misma semana)
    umbral_amarillo_pct: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    umbral_naranja_pct: Mapped[int] = mapped_column(Integer, default=75, nullable=False)
    umbral_rojo_pct: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
