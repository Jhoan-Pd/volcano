"""Declarative base and common mixins."""
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Naming convention: Alembic generates stable, readable names for indexes and constraints.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def fk(target: str, ondelete: str = "CASCADE"):
    """Required, indexed foreign key — the most repeated column shape in the models.

    fk("municipalities.id") is the same as
    mapped_column(ForeignKey("municipalities.id", ondelete="CASCADE"), index=True, nullable=False)
    """
    return mapped_column(ForeignKey(target, ondelete=ondelete), index=True, nullable=False)


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
