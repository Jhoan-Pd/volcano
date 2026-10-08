"""Generadores de datos SIMULADOS (reproducibles con semilla fija).

Todo lo que sale de aquí se guarda con es_simulado=True para que la interfaz lo advierta.

- Clima diario: solo se usa si Open-Meteo no responde. Climatología bimodal de Pasto
  (lluvias mar-may y oct-dic, verano jul-ago), gradiente térmico de -0.55 °C/100 m y
  anomalías ENSO aproximadas (La Niña 2020-2022 más húmedo; El Niño 2023-2024 más seco y cálido).
- Casos semanales: modelo Poisson-Gamma (binomial negativa) cuya media depende de la estacionalidad,
  del clima con rezagos, de la ceniza y del SO2. Así el modelo de la Fase 2 tiene señales reales
  que aprender, y la relación clima→casos es explicable en la sustentación.
"""
import math
from collections import defaultdict
from datetime import date, timedelta

import numpy as np

from app.core.epi import desplazar, iterar_semanas, semana_de

# Precipitación mensual típica de Pasto (mm/mes)
LLUVIA_MENSUAL = {1: 70, 2: 65, 3: 85, 4: 100, 5: 85, 6: 50, 7: 35, 8: 30, 9: 45, 10: 105, 11: 115, 12: 90}
ENSO = {2020: (-0.3, 1.15), 2021: (-0.3, 1.15), 2022: (-0.2, 1.10), 2023: (0.5, 0.85), 2024: (0.6, 0.80),
        2025: (0.0, 1.0), 2026: (0.2, 0.95)}  # (anomalía °C, factor de lluvia)


def simular_clima(municipio: dict, desde: date, hasta: date, hoy: date, semilla: int) -> list[dict]:
    rng = np.random.default_rng(semilla)
    alt = municipio.get("altitud_m") or 2527
    t_base = 13.6 + (2527 - alt) * 0.0055
    anomalia = 0.0
    filas = []
    d = desde
    while d <= hasta:
        dt, factor = ENSO.get(d.year, (0.0, 1.0))
        anomalia = 0.85 * anomalia + rng.normal(0, 0.45)  # persistencia AR(1)
        estacional = 0.4 * math.cos(2 * math.pi * (d.timetuple().tm_yday - 60) / 365)
        tmed = t_base + dt + estacional + anomalia
        mensual = LLUVIA_MENSUAL[d.month] * factor * (1.1 if alt < 2000 else 1.0)
        p_lluvia = 0.62 if mensual >= 80 else 0.45 if mensual >= 50 else 0.28
        lluvia = 0.0
        if rng.random() < p_lluvia:
            lluvia = float(rng.gamma(0.9, mensual / (30 * p_lluvia * 0.9)))
        tmed -= 0.04 * lluvia  # días lluviosos más frescos
        humedad = float(np.clip(76 + 0.35 * lluvia + rng.normal(0, 4) - 1.2 * (tmed - t_base), 52, 98))
        filas.append({
            "fecha": d,
            "temp_max_c": round(tmed + 5.6 + rng.normal(0, 0.8), 1),
            "temp_min_c": round(tmed - 5.1 + rng.normal(0, 0.8), 1),
            "temp_media_c": round(tmed, 1),
            "precipitacion_mm": round(lluvia, 1),
            "humedad_relativa_pct": round(humedad, 1),
            "es_pronostico": d >= hoy,
            "es_simulado": True,
            "fuente": "simulado",
        })
        d += timedelta(days=1)
    return filas


def clima_semanal(filas: list[dict]) -> dict[tuple[int, int], dict[str, float]]:
    """Agrega clima diario a semanas epidemiológicas: temperatura y humedad promedio, lluvia total."""
    grupos: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for f in filas:
        if not f["es_pronostico"]:
            grupos[semana_de(f["fecha"])].append(f)
    salida = {}
    for k, regs in grupos.items():
        def prom(c):
            v = [r[c] for r in regs if r[c] is not None]
            return sum(v) / len(v) if v else None
        lluvia = [r["precipitacion_mm"] for r in regs if r["precipitacion_mm"] is not None]
        salida[k] = {"t": prom("temp_media_c"), "h": prom("humedad_relativa_pct"), "p": sum(lluvia) if lluvia else None}
    return salida


def _media(clima: dict, campo: str) -> float:
    v = [x[campo] for x in clima.values() if x[campo] is not None]
    return float(np.mean(v)) if v else 0.0


def generar_casos(
    *, municipio: str, poblacion: int, base: dict[str, float], clima: dict, so2: dict[tuple[int, int], float],
    ceniza: dict[tuple[int, int], int], desde: tuple[int, int], hasta: tuple[int, int], semilla: int,
) -> dict[str, list[tuple[int, int, int]]]:
    """Devuelve {codigo_enfermedad: [(anio, semana, casos), ...]}."""
    rng = np.random.default_rng(semilla)
    t_m, h_m, p_m = _media(clima, "t"), _media(clima, "h"), _media(clima, "p")
    so2_m = float(np.mean(list(so2.values()))) if so2 else 400.0

    def c(a, s, lag, campo, defecto):
        v = clima.get(desplazar(a, s, -lag), {}).get(campo)
        return defecto if v is None else v

    def ceniza_rezagada(a, s):
        # efecto de la ceniza: semana del evento, y se desvanece en 2 semanas
        return sum(ceniza.get(desplazar(a, s, -lag), 0) * peso for lag, peso in ((0, 1.0), (1, 0.6), (2, 0.25)))

    salida: dict[str, list[tuple[int, int, int]]] = {k: [] for k in base}
    for a, s in iterar_semanas(desde, hasta):
        ash = ceniza_rezagada(a, s)
        so2_s = so2.get((a, s), so2_m)
        covid = 0.55 if (a == 2020 and s >= 13) else 0.8 if a == 2021 else 1.0  # menor consulta en pandemia

        # IRA: dos picos (lluvias), más casos con frío y humedad de la semana anterior
        lam_ira = base["IRA"] * (1 + 0.22 * math.cos(2 * math.pi * (s - 18) / 26))
        lam_ira *= math.exp(0.018 * (c(a, s, 1, "h", h_m) - h_m) - 0.09 * (c(a, s, 1, "t", t_m) - t_m)
                            + 0.0025 * (c(a, s, 1, "p", p_m) - p_m))
        lam_ira *= covid * (1 + 0.12 * ash)

        # EDA: lluvias fuertes con 1-2 semanas de rezago y calor
        lam_eda = base["EDA"] * math.exp(0.004 * (c(a, s, 2, "p", p_m) - p_m) + 0.0025 * (c(a, s, 1, "p", p_m) - p_m)
                                         + 0.06 * (c(a, s, 1, "t", t_m) - t_m))
        lam_eda *= 0.85 if (a == 2020 and s >= 13) else 1.0

        # DENGUE: temperatura con rezago 4 y lluvia acumulada 3-6 semanas; 2024 fue año epidémico en Colombia
        lluvia_36 = np.mean([c(a, s, k, "p", p_m) for k in range(3, 7)])
        lam_den = base["DENGUE"] * math.exp(0.35 * (c(a, s, 4, "t", t_m) - t_m) + 0.006 * (lluvia_36 - p_m))
        lam_den *= 2.2 if a == 2024 else 1.3 if a == 2023 else 1.0

        # RESPIRATORIA POR CENIZA: línea base baja + picos con ceniza (proporcional a población) + SO2
        lam_cen = base["RESP_CENIZA"] * math.exp(0.0012 * (so2_s - so2_m))
        lam_cen += ash * max(2.0, poblacion / 9000)

        for codigo, lam, k in (("IRA", lam_ira, 25), ("EDA", lam_eda, 20), ("DENGUE", lam_den, 3),
                               ("RESP_CENIZA", lam_cen, 4)):
            lam = max(lam, 0.001)
            casos = int(rng.poisson(rng.gamma(k, lam / k)))  # binomial negativa
            salida[codigo].append((a, s, casos))
    return salida
