"""Open-Meteo adapter with a mocked HTTP transport (no internet)."""
from datetime import date

import httpx
import pytest

from volcano.sources import DataSourceError, OpenMeteoSource

RESPONSE = {
    "daily": {
        "time": ["2026-10-05", "2026-10-06", "2026-10-07"],
        "temperature_2m_max": [18.2, 17.9, 19.0],
        "temperature_2m_min": [8.1, 8.4, None],
        "temperature_2m_mean": [12.9, None, None],
        "precipitation_sum": [3.4, 0.0, 12.1],
    },
    "hourly": {
        "time": ["2026-10-05T00:00", "2026-10-05T12:00", "2026-10-06T00:00"],
        "relative_humidity_2m": [90, 70, 85],
    },
    "current": {"time": "2026-10-06T15:00", "temperature_2m": 16.4, "relative_humidity_2m": 72,
                "precipitation": 0.0, "weather_code": 3, "wind_speed_10m": 9.5},
}


def _source(status=200, body=RESPONSE, log=None):
    def handler(request: httpx.Request):
        if log is not None:
            log.append(request)
        return httpx.Response(status, json=body)
    return OpenMeteoSource(client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_adapts_the_format_to_database_rows():
    rows = OpenMeteoSource.adapt_daily(RESPONSE, today=date(2026, 10, 6))
    assert len(rows) == 3
    r0, r1, r2 = rows
    assert r0["date"] == date(2026, 10, 5) and r0["relative_humidity_pct"] == 80.0
    assert r0["is_forecast"] is False and r1["is_forecast"] is True
    assert r1["temp_mean_c"] == round((17.9 + 8.4) / 2, 2)  # mean computed when missing
    assert r2["temp_mean_c"] is None and r2["precipitation_mm"] == 12.1
    assert all(r["source"] == "open-meteo" and r["is_simulated"] is False for r in rows)


def test_fetch_sends_the_right_parameters():
    requests = []
    rows = _source(log=requests).fetch(latitude=1.2136, longitude=-77.2811, mode="forecast")
    assert rows
    q = dict(requests[0].url.params)
    assert q["forecast_days"] == "16" and q["timezone"] == "America/Bogota"
    assert "precipitation_sum" in q["daily"] and q["hourly"] == "relative_humidity_2m"


def test_current_weather():
    current = _source().current(latitude=1.2, longitude=-77.3)
    assert current["temperature_c"] == 16.4 and current["description"] == "Nublado"


def test_http_error_raises_a_controlled_exception():
    with pytest.raises(DataSourceError):
        _source(status=400, body={"error": True, "reason": "bad"}).fetch(latitude=1, longitude=-77)
