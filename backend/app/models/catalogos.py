from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.texto import separar_lista
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
    # Códigos de evento INS/SIVIGILA equivalentes (separados por coma), p. ej. "210,220" para dengue
    codigos_sivigila: Mapped[str | None] = mapped_column(String(60))
    # Categorías de farmacia cuyas ventas anticipan la enfermedad, p. ej. "ANTIGRIPALES,ANTIPIRETICOS"
    categorias_farmacia: Mapped[str | None] = mapped_column(String(200))
    color: Mapped[str] = mapped_column(String(9), default="#2a78d6", nullable=False)
    # Umbrales del canal endémico (percentiles históricos de la misma semana)
    umbral_amarillo_pct: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    umbral_naranja_pct: Mapped[int] = mapped_column(Integer, default=75, nullable=False)
    umbral_rojo_pct: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Las columnas guardan listas separadas por coma; estas propiedades las exponen ya separadas
    @property
    def lista_terminos(self) -> list[str]:
        return separar_lista(self.terminos_busqueda, str.lower)

    @property
    def lista_codigos_sivigila(self) -> list[str]:
        return separar_lista(self.codigos_sivigila)

    @property
    def lista_categorias_farmacia(self) -> list[str]:
        return separar_lista(self.categorias_farmacia, str.upper)

    @property
    def lista_recomendaciones(self) -> list[str]:
        return [r.strip() for r in (self.recomendaciones or "").splitlines() if r.strip()]
