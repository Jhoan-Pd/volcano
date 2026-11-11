from datetime import date

from pydantic import BaseModel


class Thresholds(BaseModel):
    yellow: float
    orange: float
    red: float


class PredictionSummary(BaseModel):
    """What the model says about the next 4 weeks (predictive traffic light)."""
    max_level: str
    peak_week: str
    expected_cases_h1: float
    lower_bound_h1: float
    upper_bound_h1: float
    algorithm: str


class DiseaseRisk(BaseModel):
    disease_id: int
    code: str
    name: str
    color: str
    year: int
    epi_week: int
    cases: int
    previous_week_cases: int | None
    change_pct: float | None
    rate_per_100k: float
    thresholds: Thresholds
    level: str  # GREEN | YELLOW | ORANGE | RED
    is_simulated: bool
    recommendations: list[str]
    prediction: PredictionSummary | None = None


class AshFall(BaseModel):
    date: date
    municipality: str | None
    intensity: int
    description: str | None
    is_simulated: bool


class VolcanoStatus(BaseModel):
    activity_level: str
    date: date | None
    description: str | None
    bulletin_url: str | None
    is_simulated: bool
    so2_tons_per_day: float | None
    recent_ash_falls: list[AshFall]


class DashboardSummary(BaseModel):
    municipality_id: int
    municipality: str
    population: int
    reference_week: str
    risks: list[DiseaseRisk]
    volcano: VolcanoStatus
    has_simulated_data: bool


class SeriesPoint(BaseModel):
    year: int
    epi_week: int
    label: str
    week_start: date
    cases: int | None
    p_yellow: float | None
    p_orange: float | None
    p_red: float | None


class DiseaseSeries(BaseModel):
    municipality_id: int
    disease_id: int
    disease: str
    points: list[SeriesPoint]


class MunicipalityRisk(BaseModel):
    municipality_id: int
    municipality: str
    divipola_code: str
    latitude: float
    longitude: float
    max_level: str
    levels: dict[str, str]  # disease code → observed level
    max_predicted_level: str | None = None
    predicted_levels: dict[str, str] = {}  # disease code → highest level over the next 4 weeks
