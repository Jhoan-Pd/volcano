"""Pruebas del adaptador Open-Meteo con un transporte HTTP simulado (no usa internet)."""
from datetime import date

import httpx
import pytest

from app.fuentes import FuenteDatosError, OpenMeteoFuente

RESPUESTA = {
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


def _fuente(status=200, cuerpo=RESPUESTA, registro=None):
    def handler(request: httpx.Request):
        if registro is not None:
            registro.append(request)
        return httpx.Response(status, json=cuerpo)
    return OpenMeteoFuente(cliente=httpx.Client(transport=httpx.MockTransport(handler)))


def test_adapta_formato_a_filas_de_bd():
    filas = OpenMeteoFuente.adaptar_diario(RESPUESTA, hoy=date(2026, 10, 6))
    assert len(filas) == 3
    f0, f1, f2 = filas
    assert f0["fecha"] == date(2026, 10, 5) and f0["humedad_relativa_pct"] == 80.0
    assert f0["es_pronostico"] is False and f1["es_pronostico"] is True
    assert f1["temp_media_c"] == round((17.9 + 8.4) / 2, 2)  # media calculada si falta
    assert f2["temp_media_c"] is None and f2["precipitacion_mm"] == 12.1
    assert all(f["fuente"] == "open-meteo" and f["es_simulado"] is False for f in filas)


def test_obtener_envia_parametros_correctos():
    peticiones = []
    filas = _fuente(registro=peticiones).obtener(latitud=1.2136, longitud=-77.2811, modo="pronostico")
    assert filas
    q = dict(peticiones[0].url.params)
    assert q["forecast_days"] == "16" and q["timezone"] == "America/Bogota"
    assert "precipitation_sum" in q["daily"] and q["hourly"] == "relative_humidity_2m"


def test_clima_actual():
    actual = _fuente().actual(latitud=1.2, longitud=-77.3)
    assert actual["temperatura_c"] == 16.4 and actual["descripcion"] == "Nublado"


def test_error_http_lanza_excepcion_controlada():
    with pytest.raises(FuenteDatosError):
        _fuente(status=400, cuerpo={"error": True, "reason": "bad"}).obtener(latitud=1, longitud=-77)
