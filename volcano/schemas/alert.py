"""Early-alert schemas."""
from datetime import datetime

from pydantic import BaseModel, Field

from volcano.models.enums import AlertOrigin, RiskLevel


class AlertOut(BaseModel):
    id: int
    municipality_id: int
    municipality: str
    disease_id: int
    disease: str
    disease_code: str
    year: int
    epi_week: int
    label: str
    risk_level: str  # ORANGE | RED
    origin: str  # OBSERVED | PREDICTED
    message: str
    active: bool
    email_notified: bool
    created_at: datetime
    closed_at: datetime | None


class EvaluationResult(BaseModel):
    new: int
    updated: int
    closed: int
    active: int
    emails_sent: int


class AlertFilters(BaseModel):
    q: str | None = Field(None, max_length=80, description="Text in the message, municipality or disease")
    municipality_id: int | None = None
    disease_id: int | None = None
    level: RiskLevel | None = None
    origin: AlertOrigin | None = None
    active: bool | None = None
