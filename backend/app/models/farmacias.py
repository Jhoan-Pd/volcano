from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Farmacia(TimestampMixin, Base):
    __tablename__ = "farmacias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    nit: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    direccion: Mapped[str | None] = mapped_column(String(200))
    telefono: Mapped[str | None] = mapped_column(String(30))
    municipio_id: Mapped[int] = mapped_column(ForeignKey("municipios.id", ondelete="RESTRICT"), index=True, nullable=False)
    # Usuario con rol FARMACIA que reporta en nombre de esta farmacia (1 a 1)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), unique=True)
    latitud: Mapped[float | None] = mapped_column(Float)
    longitud: Mapped[float | None] = mapped_column(Float)
    activa: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    municipio: Mapped["Municipio"] = relationship(lazy="joined")  # noqa: F821


class ReporteFarmacia(TimestampMixin, Base):
    """Unidades vendidas por categoría en una semana epidemiológica."""
    __tablename__ = "reportes_farmacia"
    __table_args__ = (UniqueConstraint("farmacia_id", "anio", "semana_epi", "categoria"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farmacia_id: Mapped[int] = mapped_column(ForeignKey("farmacias.id", ondelete="CASCADE"), index=True, nullable=False)
    anio: Mapped[int] = mapped_column(Integer, nullable=False)
    semana_epi: Mapped[int] = mapped_column(Integer, nullable=False)
    categoria: Mapped[str] = mapped_column(String(30), nullable=False)  # CategoriaProducto
    unidades: Mapped[int] = mapped_column(Integer, nullable=False)
    es_simulado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
