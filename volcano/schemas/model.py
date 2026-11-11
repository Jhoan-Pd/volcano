"""Predictive-model schemas: metrics, predictions and explanations."""
from datetime import date, datetime

from pydantic import BaseModel

from volcano.schemas.dashboard import PredictionSummary, Thresholds  # noqa: F401 (re-exported)


class ModelOut(BaseModel):
    id: int
    disease_id: int
    disease: str
    algorithm: str
    version: str
    trained_at: datetime
    baseline_mae: float | None
    baseline_rmse: float | None
    model_mae: float | None
    model_rmse: float | None
    mae_improvement_pct: float | None
    sample_count: int | None
    active: bool
    importances: dict | None
    metrics: dict | None


class TrainingStatus(BaseModel):
    running: bool
    started_at: datetime | None = None
    finished_at: datetime | None = None
    message: str | None = None
    errors: list[str] = []


class ModelSummary(BaseModel):
    id: int
    algorithm: str
    trained_at: datetime
    baseline_mae: float | None
    model_mae: float | None
    baseline_rmse: float | None
    model_rmse: float | None


class PredictionPoint(BaseModel):
    year: int
    epi_week: int
    label: str
    week_start: date
    horizon: int
    expected_cases: float
    lower_bound: float
    upper_bound: float
    level: str
    thresholds: Thresholds | None


class BacktestPoint(BaseModel):
    year: int
    epi_week: int
    label: str
    observed: float
    predicted: float


class DiseasePrediction(BaseModel):
    municipality_id: int
    disease_id: int
    disease: str
    base_week: str | None
    model: ModelSummary | None
    max_level: str | None
    points: list[PredictionPoint]
    backtest: list[BacktestPoint]


class ExplanationFactor(BaseModel):
    group: str  # stable key: recent_cases, weather, searches…
    group_label: str  # Spanish label shown in the UI
    contribution: float  # cases the group adds compared with its typical value
    direction: str  # up | down | neutral
    message: str | None


class PredictionExplanation(BaseModel):
    municipality_id: int
    municipality: str
    disease_id: int
    disease: str
    label: str
    horizon: int
    level: str
    expected_cases: float
    method: str
    summary: str
    factors: list[ExplanationFactor]
    global_importance: dict | None
