"""Generators of SIMULATED data (reproducible with a fixed seed).

Everything produced here is stored with is_simulated=True so the UI can warn about it.

- Daily weather: only used when Open-Meteo does not answer. Bimodal climatology of Pasto (rain in
  Mar-May and Oct-Dec, dry season Jul-Aug), a -0.55 °C/100 m lapse rate and approximate ENSO
  anomalies (La Niña 2020-2022 wetter; El Niño 2023-2024 drier and warmer).
- Searches (Trends) and pharmacy sales: signals that lead cases by about one week.
- Weekly cases: Poisson-Gamma (negative binomial) model whose mean depends on seasonality, lagged
  weather, ash and SO₂. The model therefore has real signals to learn, and the weather → cases
  relationship can be explained in the defence.
"""
import math
from collections import defaultdict
from datetime import date, timedelta

import numpy as np

from volcano.shared.epi import EpiWeek, iter_weeks, shift, week_of, week_start

# Typical monthly rainfall in Pasto (mm/month)
MONTHLY_RAIN = {1: 70, 2: 65, 3: 85, 4: 100, 5: 85, 6: 50, 7: 35, 8: 30, 9: 45, 10: 105, 11: 115, 12: 90}
ENSO = {2020: (-0.3, 1.15), 2021: (-0.3, 1.15), 2022: (-0.2, 1.10), 2023: (0.5, 0.85), 2024: (0.6, 0.80),
        2025: (0.0, 1.0), 2026: (0.2, 0.95)}  # (°C anomaly, rain factor)


def simulate_weather(municipality: dict, since: date, until: date, today: date, seed: int) -> list[dict]:
    rng = np.random.default_rng(seed)
    altitude = municipality.get("altitude_m") or 2527
    t_base = 13.6 + (2527 - altitude) * 0.0055
    anomaly = 0.0
    rows = []
    d = since
    while d <= until:
        dt, factor = ENSO.get(d.year, (0.0, 1.0))
        anomaly = 0.85 * anomaly + rng.normal(0, 0.45)  # AR(1) persistence
        seasonal = 0.4 * math.cos(2 * math.pi * (d.timetuple().tm_yday - 60) / 365)
        t_mean = t_base + dt + seasonal + anomaly
        monthly = MONTHLY_RAIN[d.month] * factor * (1.1 if altitude < 2000 else 1.0)
        p_rain = 0.62 if monthly >= 80 else 0.45 if monthly >= 50 else 0.28
        rain = 0.0
        if rng.random() < p_rain:
            rain = float(rng.gamma(0.9, monthly / (30 * p_rain * 0.9)))
        t_mean -= 0.04 * rain  # rainy days are cooler
        humidity = float(np.clip(76 + 0.35 * rain + rng.normal(0, 4) - 1.2 * (t_mean - t_base), 52, 98))
        rows.append({
            "date": d,
            "temp_max_c": round(t_mean + 5.6 + rng.normal(0, 0.8), 1),
            "temp_min_c": round(t_mean - 5.1 + rng.normal(0, 0.8), 1),
            "temp_mean_c": round(t_mean, 1),
            "precipitation_mm": round(rain, 1),
            "relative_humidity_pct": round(humidity, 1),
            "is_forecast": d >= today,
            "is_simulated": True,
            "source": "simulated",
        })
        d += timedelta(days=1)
    return rows


def weekly_weather(rows: list[dict]) -> dict[EpiWeek, dict[str, float | None]]:
    """Aggregate daily weather into epidemiological weeks: mean temperature and humidity, total rain."""
    groups: dict[EpiWeek, list[dict]] = defaultdict(list)
    for r in rows:
        if not r["is_forecast"]:
            groups[week_of(r["date"])].append(r)
    out = {}
    for k, records in groups.items():
        rain = [r["precipitation_mm"] for r in records if r["precipitation_mm"] is not None]
        out[k] = {"t": _mean(records, "temp_mean_c"), "h": _mean(records, "relative_humidity_pct"),
                  "p": sum(rain) if rain else None}
    return out


def _mean(records: list[dict], field: str) -> float | None:
    values = [r[field] for r in records if r[field] is not None]
    return sum(values) / len(values) if values else None


def _overall_mean(weather: dict, field: str) -> float:
    values = [x[field] for x in weather.values() if x[field] is not None]
    return float(np.mean(values)) if values else 0.0


def generate_cases(  # noqa: PLR0913 - all keyword-only; bundling them in an object would not help
    *, municipality: str, population: int, baseline: dict[str, float], weather: dict, so2: dict[EpiWeek, float],
    ash: dict[EpiWeek, int], since: EpiWeek, until: EpiWeek, seed: int,
) -> dict[str, list[tuple[int, int, int]]]:
    """Returns {disease_code: [(year, week, cases), ...]}."""
    rng = np.random.default_rng(seed)
    t_m, h_m, p_m = _overall_mean(weather, "t"), _overall_mean(weather, "h"), _overall_mean(weather, "p")
    so2_m = float(np.mean(list(so2.values()))) if so2 else 400.0

    def w(y, wk, lag, field, default):
        v = weather.get(shift(y, wk, -lag), {}).get(field)
        return default if v is None else v

    def lagged_ash(y, wk):
        # ash effect: the event week, fading over 2 weeks
        return sum(ash.get(shift(y, wk, -lag), 0) * weight for lag, weight in ((0, 1.0), (1, 0.6), (2, 0.25)))

    out: dict[str, list[tuple[int, int, int]]] = {k: [] for k in baseline}
    for y, wk in iter_weeks(since, until):
        ash_effect = lagged_ash(y, wk)
        so2_week = so2.get((y, wk), so2_m)
        covid = 0.55 if (y == 2020 and wk >= 13) else 0.8 if y == 2021 else 1.0  # fewer visits in the pandemic

        # IRA: two peaks (rainy seasons), more cases with last week's cold and humidity
        lam_ira = baseline["IRA"] * (1 + 0.22 * math.cos(2 * math.pi * (wk - 18) / 26))
        lam_ira *= math.exp(0.018 * (w(y, wk, 1, "h", h_m) - h_m) - 0.09 * (w(y, wk, 1, "t", t_m) - t_m)
                            + 0.0025 * (w(y, wk, 1, "p", p_m) - p_m))
        lam_ira *= covid * (1 + 0.12 * ash_effect)

        # EDA: heavy rain with a 1-2 week lag, and heat
        lam_eda = baseline["EDA"] * math.exp(0.004 * (w(y, wk, 2, "p", p_m) - p_m)
                                             + 0.0025 * (w(y, wk, 1, "p", p_m) - p_m)
                                             + 0.06 * (w(y, wk, 1, "t", t_m) - t_m))
        lam_eda *= 0.85 if (y == 2020 and wk >= 13) else 1.0

        # DENGUE: temperature with a 4-week lag and rain over weeks 3-6; 2024 was an epidemic year in Colombia
        rain_3_6 = np.mean([w(y, wk, k, "p", p_m) for k in range(3, 7)])
        lam_den = baseline["DENGUE"] * math.exp(0.35 * (w(y, wk, 4, "t", t_m) - t_m) + 0.006 * (rain_3_6 - p_m))
        lam_den *= 2.2 if y == 2024 else 1.3 if y == 2023 else 1.0

        # ASH-RELATED RESPIRATORY: low baseline + ash peaks (proportional to population) + SO₂
        lam_ash = baseline["RESP_CENIZA"] * math.exp(0.0012 * (so2_week - so2_m))
        lam_ash += ash_effect * max(2.0, population / 9000)

        for code, lam, k in (("IRA", lam_ira, 25), ("EDA", lam_eda, 20), ("DENGUE", lam_den, 3),
                             ("RESP_CENIZA", lam_ash, 4)):
            rate = max(lam, 0.001)
            cases = int(rng.poisson(rng.gamma(k, rate / k)))  # negative binomial
            out[code].append((y, wk, cases))
    return out


# ── simulated early signals ─────────────────────────────────────────────────
# The simulated hypothesis (which the model must discover): people search for symptoms and buy
# medicine BEFORE the case reaches SIVIGILA (consultation + notification take ~1 week). Each signal
# therefore mixes the cases of week t with those of week t+1.

def _leading_series(series: dict[EpiWeek, int], y: int, wk: int, future_weight: float = 0.45) -> float:
    current = series.get((y, wk), 0)
    future = series.get(shift(y, wk, 1), current)
    return (1 - future_weight) * current + future_weight * future


def generate_trends(
    *, cases: dict[str, dict[EpiWeek, int]], terms: dict[str, list[str]], since: EpiWeek, until: EpiWeek, seed: int,
) -> list[dict]:
    """Weekly 0-100 interest per term for the whole department (like Google Trends in CO-NAR).

    `cases`: {disease_code: {(year, week): cases of the 6 municipalities}}
    `terms`: {disease_code: [search terms]}
    """
    rng = np.random.default_rng(seed)
    means = {code: (np.mean(list(s.values())) or 1.0) for code, s in cases.items() if s}
    by_term: dict[str, list[str]] = defaultdict(list)
    for code, ts in terms.items():
        for t in ts:
            by_term[t].append(code)

    rows = []
    for term, diseases in by_term.items():
        raw = {}
        noise = 0.0
        for y, wk in iter_weeks(since, until):
            signal = sum(_leading_series(cases[c], y, wk) / means[c] for c in diseases if c in cases and c in means)
            noise = 0.6 * noise + rng.normal(0, 0.10)  # search interest has inertia
            raw[(y, wk)] = max(0.0, (0.35 + signal / max(len(diseases), 1)) * math.exp(noise))
        peak = max(raw.values(), default=1.0) or 1.0
        for (y, wk), v in raw.items():
            rows.append({"term": term, "region": "CO-NAR", "year": y, "epi_week": wk,
                         "week_start": week_start(y, wk), "interest": round(100 * v / peak, 1),
                         "source": "simulated", "is_simulated": True})
    return rows


BASE_UNITS = {"COLD_FLU": 120, "ANTIPYRETICS": 150, "ORAL_REHYDRATION": 40,
              "INHALERS": 25, "FACE_MASKS": 70, "REPELLENTS": 12}


def generate_pharmacy_reports(
    *, pharmacies: list[dict], cases: dict[int, dict[str, dict[EpiWeek, int]]],
    categories: dict[str, list[str]], since: EpiWeek, until: EpiWeek, seed: int,
) -> list[dict]:
    """Units sold per pharmacy, week and category.

    `pharmacies`: [{"id", "municipality_id", "altitude_m"}]
    `cases`: {municipality_id: {disease_code: {(year, week): cases}}}
    `categories`: {disease_code: [categories whose sales rise with that disease]}
    """
    rng = np.random.default_rng(seed)
    by_category: dict[str, list[str]] = defaultdict(list)
    for code, cats in categories.items():
        for c in cats:
            by_category[c].append(code)

    rows = []
    for p in pharmacies:
        scale = float(rng.lognormal(0, 0.35))  # every pharmacy has its own sales volume
        warm = (p.get("altitude_m") or 2500) < 2000
        series = cases.get(p["municipality_id"], {})
        means = {c: max(np.mean(list(s.values())), 0.3) for c, s in series.items() if s}
        for y, wk in iter_weeks(since, until):
            if rng.random() < 0.04:
                continue  # weeks without a report (realism: not every pharmacy always reports)
            for category, units in BASE_UNITS.items():
                base = units * scale * (3.0 if category == "REPELLENTS" and warm else 1.0)
                excess = sum(0.55 * (_leading_series(series[c], y, wk) / means[c] - 1)
                             for c in by_category.get(category, []) if c in series and c in means)
                if category == "FACE_MASKS" and y == 2020 and wk >= 12:
                    base *= 4.0  # COVID-19 pandemic
                mean = max(base * (1 + excess), 0.5)
                rows.append({"pharmacy_id": p["id"], "year": y, "epi_week": wk, "category": category,
                             "units": int(rng.poisson(mean)), "is_simulated": True})
    return rows
