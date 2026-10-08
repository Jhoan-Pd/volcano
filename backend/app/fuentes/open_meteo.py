"""Adaptador de la API Open-Meteo (gratis, sin API key).

Endpoints usados:
- Pronóstico (16 días) + días pasados recientes: https://api.open-meteo.com/v1/forecast
- Histórico (reanálisis ERA5):                   https://archive-api.open-meteo.com/v1/archive

Decisión: la humedad relativa diaria se calcula como el promedio de la variable horaria
`relative_humidity_2m`, que existe en ambos endpoints; así el adaptador no depende de
variables diarias que solo ofrece uno de los dos.
"""
import time
from collections import defaultdict
from datetime import date, datetime
from typing import Any

import httpx

from app.core.config import settings
from app.fuentes.base import FuenteDatos, FuenteDatosError, logger

VARIABLES_DIARIAS = "temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum"
VARIABLES_ACTUALES = "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m"

# Códigos WMO que usa Open-Meteo -> descripción en español
CODIGOS_WMO = {
    0: "Despejado", 1: "Mayormente despejado", 2: "Parcialmente nublado", 3: "Nublado",
    45: "Niebla", 48: "Niebla con escarcha", 51: "Llovizna ligera", 53: "Llovizna", 55: "Llovizna intensa",
    61: "Lluvia ligera", 63: "Lluvia", 65: "Lluvia fuerte", 66: "Lluvia helada", 67: "Lluvia helada fuerte",
    71: "Nieve ligera", 73: "Nieve", 75: "Nieve fuerte", 80: "Chubascos ligeros", 81: "Chubascos",
    82: "Chubascos fuertes", 95: "Tormenta", 96: "Tormenta con granizo", 99: "Tormenta con granizo fuerte",
}


def describir_codigo(codigo: int | None) -> str:
    return CODIGOS_WMO.get(codigo, "Sin dato") if codigo is not None else "Sin dato"


class OpenMeteoFuente(FuenteDatos):
    nombre = "open-meteo"

    def __init__(self, cliente: httpx.Client | None = None, timeout: float | None = None):
        self._cliente = cliente
        self._timeout = timeout or settings.HTTP_TIMEOUT_SEGUNDOS

    # ── HTTP ──────────────────────────────────────────────────────────────────
    def _get(self, url: str, params: dict[str, Any], reintentos: int = 2) -> dict[str, Any]:
        ultimo_error: Exception | None = None
        for intento in range(reintentos + 1):
            try:
                if self._cliente is not None:
                    resp = self._cliente.get(url, params=params)
                else:
                    with httpx.Client(timeout=self._timeout) as c:
                        resp = c.get(url, params=params)
                if resp.status_code == 200:
                    return resp.json()
                ultimo_error = FuenteDatosError(f"HTTP {resp.status_code}: {resp.text[:200]}")
                if resp.status_code < 500 and resp.status_code != 429:
                    break  # error del cliente: no tiene sentido reintentar
            except (httpx.HTTPError, ValueError) as exc:
                ultimo_error = exc
            time.sleep(0.8 * (intento + 1))
        raise FuenteDatosError(f"Open-Meteo no respondió: {ultimo_error}")

    # ── Adaptación de formato ────────────────────────────────────────────────
    @staticmethod
    def _humedad_diaria(payload: dict[str, Any]) -> dict[str, float]:
        horario = payload.get("hourly") or {}
        tiempos, valores = horario.get("time") or [], horario.get("relative_humidity_2m") or []
        acumulado: dict[str, list[float]] = defaultdict(list)
        for t, v in zip(tiempos, valores):
            if v is not None:
                acumulado[t[:10]].append(float(v))
        return {dia: round(sum(vs) / len(vs), 1) for dia, vs in acumulado.items() if vs}

    @classmethod
    def adaptar_diario(cls, payload: dict[str, Any], hoy: date | None = None) -> list[dict[str, Any]]:
        diario = payload.get("daily")
        if not diario or "time" not in diario:
            raise FuenteDatosError("Respuesta de Open-Meteo sin bloque 'daily'")
        hoy = hoy or date.today()
        humedad = cls._humedad_diaria(payload)
        filas = []
        for i, dia in enumerate(diario["time"]):
            def val(clave: str):
                serie = diario.get(clave) or []
                return None if i >= len(serie) or serie[i] is None else round(float(serie[i]), 2)

            tmax, tmin, tmed = val("temperature_2m_max"), val("temperature_2m_min"), val("temperature_2m_mean")
            if tmed is None and tmax is not None and tmin is not None:
                tmed = round((tmax + tmin) / 2, 2)
            if tmax is None and tmin is None and val("precipitation_sum") is None:
                continue  # el reanálisis deja nulos los últimos días: no se guardan filas vacías
            fecha = date.fromisoformat(dia)
            filas.append({
                "fecha": fecha,
                "temp_max_c": tmax,
                "temp_min_c": tmin,
                "temp_media_c": tmed,
                "precipitacion_mm": val("precipitation_sum"),
                "humedad_relativa_pct": humedad.get(dia),
                "es_pronostico": fecha >= hoy,  # el día en curso aún no está completo
                "es_simulado": False,
                "fuente": cls.nombre,
            })
        return filas

    # ── API pública (Strategy) ───────────────────────────────────────────────
    def obtener(self, *, latitud: float, longitud: float, modo: str = "pronostico",
                desde: date | None = None, hasta: date | None = None,
                dias_pasados: int = 14, dias_pronostico: int = 16) -> list[dict[str, Any]]:
        """modo='pronostico': últimos `dias_pasados` + 16 días futuros.
        modo='historico': rango [desde, hasta] del reanálisis ERA5."""
        base = {"latitude": latitud, "longitude": longitud, "timezone": "America/Bogota",
                "daily": VARIABLES_DIARIAS, "hourly": "relative_humidity_2m"}
        if modo == "historico":
            if not desde or not hasta:
                raise ValueError("El modo histórico requiere 'desde' y 'hasta'")
            params = {**base, "start_date": desde.isoformat(), "end_date": hasta.isoformat()}
            payload = self._get(settings.OPEN_METEO_ARCHIVE_URL, params)
        else:
            params = {**base, "past_days": dias_pasados, "forecast_days": dias_pronostico}
            payload = self._get(settings.OPEN_METEO_FORECAST_URL, params)
        filas = self.adaptar_diario(payload)
        logger.info("Open-Meteo %s (%.4f, %.4f): %d días", modo, latitud, longitud, len(filas))
        return filas

    def actual(self, *, latitud: float, longitud: float) -> dict[str, Any]:
        payload = self._get(settings.OPEN_METEO_FORECAST_URL, {
            "latitude": latitud, "longitude": longitud, "timezone": "America/Bogota",
            "current": VARIABLES_ACTUALES,
        }, reintentos=1)
        cur = payload.get("current") or {}
        if not cur:
            raise FuenteDatosError("Respuesta de Open-Meteo sin bloque 'current'")
        codigo = cur.get("weather_code")
        return {
            "hora": datetime.fromisoformat(cur["time"]) if cur.get("time") else None,
            "temperatura_c": cur.get("temperature_2m"),
            "humedad_relativa_pct": cur.get("relative_humidity_2m"),
            "precipitacion_mm": cur.get("precipitation"),
            "viento_kmh": cur.get("wind_speed_10m"),
            "codigo_tiempo": codigo,
            "descripcion": describir_codigo(codigo),
        }

    def verificar(self) -> None:
        self.actual(latitud=1.2136, longitud=-77.2811)
