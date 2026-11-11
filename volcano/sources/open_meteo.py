"""Open-Meteo API adapter (free, no API key).

Endpoints:
- Forecast (16 days) + recent past days: https://api.open-meteo.com/v1/forecast
- History (ERA5 reanalysis):             https://archive-api.open-meteo.com/v1/archive

Daily relative humidity is the mean of the hourly `relative_humidity_2m` variable, which both
endpoints offer, so the adapter does not depend on a daily variable only one of them has.
"""
from collections import defaultdict
from datetime import date, datetime
from typing import Any, Literal

import httpx

from volcano.shared.config import settings
from volcano.sources.base import DataSource, DataSourceError, logger
from volcano.sources.http import get_json

DAILY_VARIABLES = "temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum"
CURRENT_VARIABLES = "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m"

# WMO weather codes used by Open-Meteo → Spanish description shown in the UI
WMO_DESCRIPTIONS_ES = {
    0: "Despejado", 1: "Mayormente despejado", 2: "Parcialmente nublado", 3: "Nublado",
    45: "Niebla", 48: "Niebla con escarcha", 51: "Llovizna ligera", 53: "Llovizna", 55: "Llovizna intensa",
    61: "Lluvia ligera", 63: "Lluvia", 65: "Lluvia fuerte", 66: "Lluvia helada", 67: "Lluvia helada fuerte",
    71: "Nieve ligera", 73: "Nieve", 75: "Nieve fuerte", 80: "Chubascos ligeros", 81: "Chubascos",
    82: "Chubascos fuertes", 95: "Tormenta", 96: "Tormenta con granizo", 99: "Tormenta con granizo fuerte",
}

Mode = Literal["forecast", "history"]


def describe_weather_code(code: int | None) -> str:
    return WMO_DESCRIPTIONS_ES.get(code, "Sin dato") if code is not None else "Sin dato"


def _day_value(daily: dict[str, Any], key: str, i: int) -> float | None:
    """Value of day i in an Open-Meteo daily series (None when missing)."""
    series = daily.get(key) or []
    return None if i >= len(series) or series[i] is None else round(float(series[i]), 2)


class OpenMeteoSource(DataSource):
    name = "open-meteo"

    def __init__(self, client: httpx.Client | None = None, timeout: float | None = None):
        self._client = client
        self._timeout = timeout or settings.HTTP_TIMEOUT_SECONDS

    def _get(self, url: str, params: dict[str, Any], retries: int = 2) -> dict[str, Any]:
        return get_json(url, params, client=self._client, timeout=self._timeout, retries=retries,
                        source="Open-Meteo")

    # ── format adaptation ────────────────────────────────────────────────────
    @staticmethod
    def _daily_humidity(payload: dict[str, Any]) -> dict[str, float]:
        hourly = payload.get("hourly") or {}
        times, values = hourly.get("time") or [], hourly.get("relative_humidity_2m") or []
        acc: dict[str, list[float]] = defaultdict(list)
        for t, v in zip(times, values, strict=False):  # the API could truncate one of the two
            if v is not None:
                acc[t[:10]].append(float(v))
        return {day: round(sum(vs) / len(vs), 1) for day, vs in acc.items() if vs}

    @classmethod
    def adapt_daily(cls, payload: dict[str, Any], today: date | None = None) -> list[dict[str, Any]]:
        daily = payload.get("daily")
        if not daily or "time" not in daily:
            raise DataSourceError("Open-Meteo response without a 'daily' block")
        today = today or date.today()
        humidity = cls._daily_humidity(payload)
        rows = []
        for i, day in enumerate(daily["time"]):
            def val(key: str, i: int = i):  # i bound as a default so the closure does not follow the loop
                return _day_value(daily, key, i)

            tmax, tmin, tmean = val("temperature_2m_max"), val("temperature_2m_min"), val("temperature_2m_mean")
            if tmean is None and tmax is not None and tmin is not None:
                tmean = round((tmax + tmin) / 2, 2)
            if tmax is None and tmin is None and val("precipitation_sum") is None:
                continue  # the reanalysis leaves the last days empty: do not store empty rows
            when = date.fromisoformat(day)
            rows.append({
                "date": when,
                "temp_max_c": tmax,
                "temp_min_c": tmin,
                "temp_mean_c": tmean,
                "precipitation_mm": val("precipitation_sum"),
                "relative_humidity_pct": humidity.get(day),
                "is_forecast": when >= today,  # the current day is not complete yet
                "is_simulated": False,
                "source": cls.name,
            })
        return rows

    # ── public API (Strategy) ────────────────────────────────────────────────
    def fetch(self, *, latitude: float, longitude: float, mode: Mode = "forecast",
              since: date | None = None, until: date | None = None,
              past_days: int = 14, forecast_days: int = 16) -> list[dict[str, Any]]:
        """mode='forecast': last `past_days` + 16 future days. mode='history': ERA5 range [since, until]."""
        base = {"latitude": latitude, "longitude": longitude, "timezone": "America/Bogota",
                "daily": DAILY_VARIABLES, "hourly": "relative_humidity_2m"}
        if mode == "history":
            if not since or not until:
                raise ValueError("History mode needs 'since' and 'until'")
            params = {**base, "start_date": since.isoformat(), "end_date": until.isoformat()}
            payload = self._get(settings.OPEN_METEO_ARCHIVE_URL, params)
        else:
            params = {**base, "past_days": past_days, "forecast_days": forecast_days}
            payload = self._get(settings.OPEN_METEO_FORECAST_URL, params)
        rows = self.adapt_daily(payload)
        logger.info("Open-Meteo %s (%.4f, %.4f): %d days", mode, latitude, longitude, len(rows))
        return rows

    def current(self, *, latitude: float, longitude: float) -> dict[str, Any]:
        payload = self._get(settings.OPEN_METEO_FORECAST_URL, {
            "latitude": latitude, "longitude": longitude, "timezone": "America/Bogota",
            "current": CURRENT_VARIABLES,
        }, retries=1)
        cur = payload.get("current") or {}
        if not cur:
            raise DataSourceError("Open-Meteo response without a 'current' block")
        code = cur.get("weather_code")
        return {
            "observed_at": datetime.fromisoformat(cur["time"]) if cur.get("time") else None,
            "temperature_c": cur.get("temperature_2m"),
            "relative_humidity_pct": cur.get("relative_humidity_2m"),
            "precipitation_mm": cur.get("precipitation"),
            "wind_kmh": cur.get("wind_speed_10m"),
            "weather_code": code,
            "description": describe_weather_code(code),
        }

    def check(self) -> None:
        self.current(latitude=1.2136, longitude=-77.2811)
