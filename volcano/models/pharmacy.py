from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from volcano.db.base import Base, TimestampMixin, fk


class Pharmacy(TimestampMixin, Base):
    __tablename__ = "pharmacies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    tax_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)  # Colombian NIT
    address: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(30))
    municipality_id: Mapped[int] = fk("municipalities.id", ondelete="RESTRICT")
    # User with the PHARMACY role who reports on behalf of this pharmacy (one to one)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), unique=True)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    municipality: Mapped["Municipality"] = relationship(lazy="joined")  # noqa: F821


class PharmacyReport(TimestampMixin, Base):
    """Units sold per product category during one epidemiological week."""
    __tablename__ = "pharmacy_reports"
    __table_args__ = (UniqueConstraint("pharmacy_id", "year", "epi_week", "category"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pharmacy_id: Mapped[int] = fk("pharmacies.id")
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    epi_week: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)  # ProductCategory
    units: Mapped[int] = mapped_column(Integer, nullable=False)
    # Who saved or last edited the report (audit trail)
    reported_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
