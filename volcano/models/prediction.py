"""Trained models, predictions and alerts."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from volcano.db.base import Base, TimestampMixin, fk, utc_now
from volcano.models.enums import AlertOrigin


class TrainedModel(TimestampMixin, Base):
    __tablename__ = "trained_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    disease_id: Mapped[int] = fk("diseases.id")
    algorithm: Mapped[str] = mapped_column(String(60), nullable=False)
    version: Mapped[str] = mapped_column(String(30), nullable=False)
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    baseline_mae: Mapped[float | None] = mapped_column(Float)
    baseline_rmse: Mapped[float | None] = mapped_column(Float)
    model_mae: Mapped[float | None] = mapped_column(Float)
    model_rmse: Mapped[float | None] = mapped_column(Float)
    sample_count: Mapped[int | None] = mapped_column(Integer)
    importances: Mapped[dict | None] = mapped_column(JSON)
    parameters: Mapped[dict | None] = mapped_column(JSON)
    # Serialized model (joblib). Deferred: not downloaded every time the row is read
    artifact: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Prediction(TimestampMixin, Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_id: Mapped[int] = fk("trained_models.id")
    municipality_id: Mapped[int] = fk("municipalities.id")
    disease_id: Mapped[int] = fk("diseases.id")
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    epi_week: Mapped[int] = mapped_column(Integer, nullable=False)
    horizon: Mapped[int] = mapped_column(Integer, nullable=False)  # 1..4 weeks ahead
    expected_cases: Mapped[float] = mapped_column(Float, nullable=False)
    lower_bound: Mapped[float] = mapped_column(Float, nullable=False)
    upper_bound: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(10), nullable=False)
    explanation: Mapped[dict | None] = mapped_column(JSON)


class Alert(TimestampMixin, Base):
    __tablename__ = "alerts"
    __table_args__ = (Index("ix_alerts_municipality_disease_week", "municipality_id", "disease_id", "year",
                            "epi_week"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    municipality_id: Mapped[int] = fk("municipalities.id")
    disease_id: Mapped[int] = fk("diseases.id")
    prediction_id: Mapped[int | None] = mapped_column(ForeignKey("predictions.id", ondelete="SET NULL"))
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    epi_week: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(10), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)  # Spanish, shown to the user
    # OBSERVED: last week's cases are above the threshold · PREDICTED: the model anticipates it
    origin: Mapped[str] = mapped_column(String(10), default=AlertOrigin.PREDICTED.value,
                                        server_default=AlertOrigin.PREDICTED.value, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_notified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    municipality: Mapped["Municipality"] = relationship(lazy="joined")  # noqa: F821
    disease: Mapped["Disease"] = relationship(lazy="joined")  # noqa: F821
