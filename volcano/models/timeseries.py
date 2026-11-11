"""Input time series of the model."""
from datetime import date

from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from volcano.db.base import Base, TimestampMixin, fk


class WeatherRecord(TimestampMixin, Base):
    """Daily weather per municipality (Open-Meteo history and forecast)."""
    __tablename__ = "weather_records"
    __table_args__ = (UniqueConstraint("municipality_id", "date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    municipality_id: Mapped[int] = fk("municipalities.id")
    date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    temp_max_c: Mapped[float | None] = mapped_column(Float)
    temp_min_c: Mapped[float | None] = mapped_column(Float)
    temp_mean_c: Mapped[float | None] = mapped_column(Float)
    precipitation_mm: Mapped[float | None] = mapped_column(Float)
    relative_humidity_pct: Mapped[float | None] = mapped_column(Float)
    is_forecast: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source: Mapped[str] = mapped_column(String(40), default="open-meteo", nullable=False)


class SearchTrend(TimestampMixin, Base):
    """Weekly Google Trends interest (0-100) per term and region."""
    __tablename__ = "search_trends"
    __table_args__ = (UniqueConstraint("term", "region", "year", "epi_week"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    term: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    region: Mapped[str] = mapped_column(String(10), default="CO-NAR", nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    epi_week: Mapped[int] = mapped_column(Integer, nullable=False)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    interest: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="pytrends", nullable=False)  # pytrends|csv|simulated
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class OfficialCase(TimestampMixin, Base):
    """Weekly notified cases (SIVIGILA/INS) per municipality and disease."""
    __tablename__ = "official_cases"
    __table_args__ = (UniqueConstraint("municipality_id", "disease_id", "year", "epi_week"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    municipality_id: Mapped[int] = fk("municipalities.id")
    disease_id: Mapped[int] = fk("diseases.id")
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    epi_week: Mapped[int] = mapped_column(Integer, nullable=False)
    cases: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(40), default="SIVIGILA", nullable=False)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class VolcanicEvent(TimestampMixin, Base):
    """Galeras activity bulletins and ash-fall events (recorded by the administrator)."""
    __tablename__ = "volcanic_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)  # VolcanicEventType
    activity_level: Mapped[str] = mapped_column(String(10), nullable=False)  # VolcanoLevel
    start_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)
    municipality_id: Mapped[int | None] = mapped_column(ForeignKey("municipalities.id", ondelete="SET NULL"),
                                                        index=True)
    ash_intensity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 0 none … 3 heavy
    so2_tons_per_day: Mapped[float | None] = mapped_column(Float)
    description: Mapped[str | None] = mapped_column(Text)
    bulletin_url: Mapped[str | None] = mapped_column(String(400))
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    recorded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    municipality: Mapped["Municipality | None"] = relationship(lazy="joined")  # noqa: F821
