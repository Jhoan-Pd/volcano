"""REST/WebSocket shapes of what the gRPC engine returns (what the browser sees)."""
from pydantic import BaseModel, Field

from volcano.schemas.dashboard import Thresholds


class EngineStatusOut(BaseModel):
    available: bool
    version: str | None = None
    models_in_memory: int = 0
    training: bool = False
    uptime_s: float | None = None
    rpcs_served: int = 0
    latency_ms: float | None = Field(None, description="Round trip gateway → engine → gateway")
    message: str | None = None


class EnginePoint(BaseModel):
    year: int
    epi_week: int
    label: str
    horizon: int
    expected_cases: float
    lower_bound: float
    upper_bound: float
    level: str | None
    thresholds: Thresholds | None = None


class EngineForecast(BaseModel):
    municipality_id: int
    municipality: str
    disease_id: int
    disease: str
    algorithm: str
    model_id: int
    base_week: str
    max_level: str | None
    points: list[EnginePoint]
    duration_ms: float = Field(description="Computation time inside the engine")
    from_cache: bool = Field(description="The model was already loaded in memory")


class TrainingProgressOut(BaseModel):
    stage: str
    message: str
    percent: float
    disease: str | None = None
    algorithm: str | None = None
    mae: float | None = None
    baseline_mae: float | None = None


class LiveAlert(BaseModel):
    id: int
    municipality_id: int
    municipality: str
    disease_id: int
    disease: str
    week: str
    level: str | None
    origin: str
    message: str


class AlertEventOut(BaseModel):
    kind: str = Field(description="ACTIVE | CREATED | UPDATED | CLOSED")
    at: str
    alert: LiveAlert


class UploadRowIn(BaseModel):
    """One CSV row already parsed and checked in the browser by the Web Worker."""
    row: int = Field(ge=1)
    pharmacy_id: int | None = None
    year: int = Field(ge=2015, le=2100)
    epi_week: int = Field(ge=1, le=53)
    category: str = Field(min_length=1, max_length=40)
    units: int = Field(ge=0, le=1_000_000)


class PharmacyUploadIn(BaseModel):
    rows: list[UploadRowIn] = Field(min_length=1, max_length=20_000)


class RowErrorOut(BaseModel):
    row: int
    message: str


class UploadSummaryOut(BaseModel):
    rows_received: int
    rows_rejected: int
    weeks_created: int
    weeks_updated: int
    weeks_rejected: int
    errors: list[RowErrorOut]
    duration_ms: float


class ScenarioIn(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    municipality_id: int
    disease_id: int
    temperature_delta_c: float = 0
    rain_change_pct: float = 0
    search_change_pct: float = 0
    pharmacy_change_pct: float = 0
    ash_fall: bool = False


class ScenarioResultOut(BaseModel):
    id: str
    municipality_id: int
    disease_id: int
    baseline: list[EnginePoint]
    scenario: list[EnginePoint]
    max_level: str | None
    change_pct: float
    summary: str
    duration_ms: float
    error: str | None = None


class RefreshResultOut(BaseModel):
    predictions: int
    alerts_new: int
    alerts_updated: int
    alerts_closed: int
    alerts_active: int
    emails_sent: int
