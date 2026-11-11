"""Schemas of data-source synchronization and CSV import."""
from datetime import date

from pydantic import BaseModel


class TrendSyncResult(BaseModel):
    source: str  # pytrends | csv | cache
    terms: list[str]
    saved_rows: int
    from_cache: list[str]
    errors: list[str]


class TrendPoint(BaseModel):
    year: int
    epi_week: int
    label: str
    week_start: date
    interest: float
    source: str
    is_simulated: bool


class TrendSeries(BaseModel):
    term: str
    region: str
    points: list[TrendPoint]


class SivigilaSyncResult(BaseModel):
    diseases: list[str]
    years_covered: list[int]
    saved_rows: int
    weeks_with_cases: int
    errors: list[str]


class RowError(BaseModel):
    row: int
    message: str


class ImportResult(BaseModel):
    kind: str
    rows_read: int
    inserted: int
    updated: int
    errors: list[RowError]


class SourceStatus(BaseModel):
    source: str
    table: str
    rows: int
    simulated: int
    latest_week: str | None
    last_updated: str | None


class DataStatus(BaseModel):
    sources: list[SourceStatus]
