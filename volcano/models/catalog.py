from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from volcano.db.base import Base, TimestampMixin
from volcano.shared.text import split_list


class Municipality(TimestampMixin, Base):
    __tablename__ = "municipalities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    divipola_code: Mapped[str] = mapped_column(String(5), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    department: Mapped[str] = mapped_column(String(60), default="Nariño", nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    altitude_m: Mapped[int | None] = mapped_column(Integer)
    population: Mapped[int] = mapped_column(Integer, nullable=False)
    crater_distance_km: Mapped[float | None] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Disease(TimestampMixin, Base):
    __tablename__ = "diseases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    icd10_code: Mapped[str | None] = mapped_column(String(40))
    recommendations: Mapped[str | None] = mapped_column(Text)  # one recommendation per line
    search_terms: Mapped[str | None] = mapped_column(String(300))  # comma-separated
    # Equivalent INS/SIVIGILA event codes (comma-separated), e.g. "210,220" for dengue
    sivigila_codes: Mapped[str | None] = mapped_column(String(60))
    # Pharmacy categories whose sales anticipate the disease, e.g. "COLD_FLU,ANTIPYRETICS"
    pharmacy_categories: Mapped[str | None] = mapped_column(String(200))
    color: Mapped[str] = mapped_column(String(9), default="#2a78d6", nullable=False)
    # Endemic channel thresholds (historical percentiles of the same week)
    yellow_threshold_pct: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    orange_threshold_pct: Mapped[int] = mapped_column(Integer, default=75, nullable=False)
    red_threshold_pct: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # The columns store comma-separated lists; these properties expose them already split
    @property
    def search_term_list(self) -> list[str]:
        return split_list(self.search_terms, str.lower)

    @property
    def sivigila_code_list(self) -> list[str]:
        return split_list(self.sivigila_codes)

    @property
    def pharmacy_category_list(self) -> list[str]:
        return split_list(self.pharmacy_categories, str.upper)

    @property
    def recommendation_list(self) -> list[str]:
        return [r.strip() for r in (self.recommendations or "").splitlines() if r.strip()]
