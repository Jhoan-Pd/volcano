"""Weather: syncs Open-Meteo with the database and serves current, forecast and weekly weather."""
import logging
import time
from collections import defaultdict
from datetime import date, timedelta

from volcano.models import Municipality
from volcano.repositories.domain import MunicipalityRepository, WeatherRecordRepository
from volcano.schemas.weather import CurrentWeather, DailyWeather, WeatherSyncResult, WeeklyWeather
from volcano.shared.epi import EpiWeek, label, last_complete_week, shift, week_of, week_start
from volcano.shared.errors import NotFoundError
from volcano.sources import DataSource, DataSourceError, OpenMeteoSource

logger = logging.getLogger("volcano.weather")

# In-memory cache of the current weather: avoids calling Open-Meteo on every dashboard visit
_CURRENT_CACHE: dict[int, tuple[float, CurrentWeather]] = {}
CURRENT_TTL_S = 600


class WeatherService:
    def __init__(self, db, source: DataSource | None = None):
        self.db = db
        self.source: OpenMeteoSource = source or OpenMeteoSource()  # injectable Strategy (tests use a fake)
        self.municipalities = MunicipalityRepository(db)
        self.records = WeatherRecordRepository(db)

    def _municipality(self, municipality_id: int) -> Municipality:
        m = self.municipalities.get(municipality_id)
        if m is None:
            raise NotFoundError(f"Municipio {municipality_id} no existe")
        return m

    # ── synchronization ──────────────────────────────────────────────────────
    def sync_municipality(self, m: Municipality, past_days: int = 14) -> int:
        rows = self.source.fetch(latitude=m.latitude, longitude=m.longitude, mode="forecast", past_days=past_days)
        return self.records.upsert_days(m.id, rows)

    def sync(self, past_days: int = 14) -> WeatherSyncResult:
        total, errors = 0, []
        municipalities = self.municipalities.active()
        for m in municipalities:
            try:
                total += self.sync_municipality(m, past_days)
            except DataSourceError as exc:
                logger.warning("Weather %s: %s", m.name, exc)
                errors.append(f"{m.name}: {exc}")
        return WeatherSyncResult(municipalities=len(municipalities), saved_rows=total, errors=errors)

    def load_real_history(self, m: Municipality, since: date, until: date) -> int:
        rows = self.source.fetch(latitude=m.latitude, longitude=m.longitude, mode="history", since=since, until=until)
        return self.records.upsert_days(m.id, rows)

    # ── queries ──────────────────────────────────────────────────────────────
    def current(self, municipality_id: int) -> CurrentWeather:
        m = self._municipality(municipality_id)
        cached = _CURRENT_CACHE.get(m.id)
        if cached and time.time() - cached[0] < CURRENT_TTL_S:
            return cached[1]
        try:
            data = self.source.current(latitude=m.latitude, longitude=m.longitude)
            result = CurrentWeather(municipality_id=m.id, municipality=m.name, source="open-meteo", **data)
            _CURRENT_CACHE[m.id] = (time.time(), result)
            return result
        except DataSourceError as exc:
            # Fallback: last observed record in the database (the dashboard is never empty)
            logger.warning("Live current weather failed (%s); using the database", exc)
            r = self.records.latest_observed(m.id)
            return CurrentWeather(
                municipality_id=m.id, municipality=m.name, observed_at=None,
                temperature_c=r.temp_mean_c if r else None,
                relative_humidity_pct=r.relative_humidity_pct if r else None,
                precipitation_mm=r.precipitation_mm if r else None, wind_kmh=None, weather_code=None,
                description=f"Último registro guardado ({r.date.isoformat()})" if r else "Sin datos",
                source="database",
            )

    def forecast(self, municipality_id: int, days: int = 16) -> list[DailyWeather]:
        m = self._municipality(municipality_id)
        today = date.today()
        rows = self.records.between(m.id, today, today + timedelta(days=days - 1))
        if len(rows) < min(days, 7):
            # No fresh forecast: try to bring it from Open-Meteo right now
            try:
                self.sync_municipality(m, past_days=1)
                rows = self.records.between(m.id, today, today + timedelta(days=days - 1))
            except DataSourceError as exc:
                logger.warning("Could not refresh the forecast: %s", exc)
        return [DailyWeather.model_validate(r) for r in rows]

    def weekly(self, municipality_id: int, weeks: int = 52) -> list[WeeklyWeather]:
        """Aggregate the observed daily weather into epidemiological weeks."""
        m = self._municipality(municipality_id)
        end = last_complete_week()
        since = week_start(*shift(*end, -(weeks - 1)))
        rows = [r for r in self.records.between(m.id, since) if not r.is_forecast]
        groups: dict[EpiWeek, list] = defaultdict(list)
        for r in rows:
            groups[week_of(r.date)].append(r)

        def mean(values):
            values = [v for v in values if v is not None]
            return round(sum(values) / len(values), 2) if values else None

        out = []
        for (y, w), records in sorted(groups.items()):
            if (y, w) > end:
                continue
            rain = [r.precipitation_mm for r in records if r.precipitation_mm is not None]
            out.append(WeeklyWeather(
                year=y, epi_week=w, label=label(y, w),
                temp_mean_c=mean([r.temp_mean_c for r in records]),
                precipitation_mm=round(sum(rain), 1) if rain else None,
                relative_humidity_pct=mean([r.relative_humidity_pct for r in records]),
            ))
        return out
