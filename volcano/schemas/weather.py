from datetime import date, datetime

from pydantic import BaseModel

from volcano.schemas.common import ORMModel


class DailyWeather(ORMModel):
    date: date
    temp_max_c: float | None
    temp_min_c: float | None
    temp_mean_c: float | None
    precipitation_mm: float | None
    relative_humidity_pct: float | None
    is_forecast: bool
    is_simulated: bool
    source: str


class CurrentWeather(BaseModel):
    municipality_id: int
    municipality: str
    observed_at: datetime | None
    temperature_c: float | None
    relative_humidity_pct: float | None
    precipitation_mm: float | None
    wind_kmh: float | None
    weather_code: int | None
    description: str
    source: str  # "open-meteo" (live) or "database" (last stored record)


class WeeklyWeather(BaseModel):
    year: int
    epi_week: int
    label: str
    temp_mean_c: float | None
    precipitation_mm: float | None
    relative_humidity_pct: float | None


class WeatherSyncResult(BaseModel):
    municipalities: int
    saved_rows: int
    errors: list[str]
