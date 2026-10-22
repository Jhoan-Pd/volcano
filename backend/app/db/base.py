"""Clase base declarativa y mixins comunes."""
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Convención de nombres: Alembic genera nombres de índices/llaves estables y legibles.
NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def fk(destino: str, ondelete: str = "CASCADE"):
    """Clave foránea obligatoria e indexada: la columna que más se repetía en los modelos.

    fk("municipios.id") equivale a
    mapped_column(ForeignKey("municipios.id", ondelete="CASCADE"), index=True, nullable=False)
    """
    return mapped_column(ForeignKey(destino, ondelete=ondelete), index=True, nullable=False)


def ahora_utc() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


class TimestampMixin:
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc, nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=ahora_utc, onupdate=ahora_utc, nullable=False
    )
