"""Weekly dataset (municipality × epidemiological week) used to train and apply the models.

Each row is "what is known when week t closes" in one municipality. Every feature uses data
from week t or earlier and the targets are the cases of t+1 … t+4, so there is no leakage
(the bug of the XGBoost model in the previous system).

Feature groups (the groups are also used to explain predictions):
    recent_cases   lags 0-3 of log(1+cases), 4- and 8-week moving averages, rate per 100k
    seasonality    cases in the same weeks of the previous year, sine/cosine of the week
    weather        temperature, rain and humidity with lags (dengue: 4-6 weeks)
    searches       Google Trends interest for the disease's terms and its change
    pharmacy       sales index of the associated product categories
    volcano        SO₂ from the bulletin and ash fall in the municipality (lags 0-3)
    municipality   population and altitude
"""
import math
from collections import defaultdict
from collections.abc import Callable

import numpy as np
import pandas as pd
from sqlalchemy import select

from volcano.ml.features import FEATURES, HORIZONS, TARGETS
from volcano.models import Disease, OfficialCase, VolcanicEvent, WeatherRecord
from volcano.models.enums import VolcanicEventType
from volcano.repositories.domain import MunicipalityRepository
from volcano.services.search_trends import SearchTrendService
from volcano.shared.epi import EpiWeek, iter_weeks, shift, week_of
from volcano.sources.pharmacy import PharmacySource

WeeklyKey = tuple[int, int, int]  # (municipality_id, year, week)



def _municipality_key(municipality_id: int) -> Callable[[EpiWeek], WeeklyKey]:
    """Turns (year, week) into the (municipality, year, week) key of the weather, pharmacy and ash dicts."""
    def key(week: EpiWeek) -> WeeklyKey:
        return (municipality_id, *week)
    return key


class DatasetBuilder:
    def __init__(self, db):
        self.db = db

    # ── raw series ───────────────────────────────────────────────────────────
    def _cases(self, disease_id: int) -> pd.DataFrame:
        rows = self.db.execute(select(OfficialCase.municipality_id, OfficialCase.year, OfficialCase.epi_week,
                                      OfficialCase.cases).where(OfficialCase.disease_id == disease_id)).all()
        return pd.DataFrame(rows, columns=["municipality_id", "year", "epi_week", "cases"])

    def _weather(self) -> dict[WeeklyKey, dict[str, float]]:
        rows = self.db.execute(select(WeatherRecord.municipality_id, WeatherRecord.date, WeatherRecord.temp_mean_c,
                                      WeatherRecord.precipitation_mm, WeatherRecord.relative_humidity_pct)
                               .where(WeatherRecord.is_forecast.is_(False))).all()
        acc: dict[WeeklyKey, list] = defaultdict(list)
        for mid, day, t, p, h in rows:
            acc[(mid, *week_of(day))].append((t, p, h))

        def mean(values):
            values = [v for v in values if v is not None]
            return float(np.mean(values)) if values else np.nan

        return {k: {"t": mean([x[0] for x in v]),
                    "p": float(np.nansum([x[1] for x in v if x[1] is not None]))
                    if any(x[1] is not None for x in v) else np.nan,
                    "h": mean([x[2] for x in v])}
                for k, v in acc.items()}

    def _volcano(self) -> tuple[dict[EpiWeek, float], dict[WeeklyKey, int]]:
        so2: dict[EpiWeek, list[float]] = defaultdict(list)
        ash: dict[WeeklyKey, int] = {}
        for e in self.db.scalars(select(VolcanicEvent)):
            week = week_of(e.start_date)
            if e.so2_tons_per_day is not None:
                so2[week].append(e.so2_tons_per_day)
            if e.event_type == VolcanicEventType.ASH_FALL and e.municipality_id:
                key = (e.municipality_id, *week)
                ash[key] = max(ash.get(key, 0), e.ash_intensity)
        return {k: float(np.mean(v)) for k, v in so2.items()}, ash

    def _pharmacy(self, disease: Disease) -> dict[WeeklyKey, float]:
        categories = disease.pharmacy_category_list
        if not categories:
            return {}
        acc: dict[WeeklyKey, list[float]] = defaultdict(list)
        for r in PharmacySource(self.db).fetch(categories=categories):
            if r["sales_index"] is not None:
                acc[(r["municipality_id"], r["year"], r["epi_week"])].append(r["sales_index"])
        return {k: float(np.mean(v)) for k, v in acc.items()}

    # ── dataset ──────────────────────────────────────────────────────────────
    def build(self, disease: Disease) -> pd.DataFrame:
        cases = self._cases(disease.id)
        if cases.empty:
            return pd.DataFrame(columns=["municipality_id", "year", "epi_week", "cases", *FEATURES, *TARGETS])
        ordered = cases.sort_values(["year", "epi_week"])
        first = tuple(ordered.iloc[0][["year", "epi_week"]].astype(int))
        last = tuple(ordered.iloc[-1][["year", "epi_week"]].astype(int))
        weeks = list(iter_weeks(first, last))
        week_index = {k: i for i, k in enumerate(weeks)}

        weather = self._weather()
        so2, ash = self._volcano()
        searches = SearchTrendService(self.db).weekly_interest(disease)
        pharmacy = self._pharmacy(disease)
        municipalities = {m.id: m for m in MunicipalityRepository(self.db).active()}

        blocks = []
        for mid, group in cases.groupby("municipality_id"):
            m = municipalities.get(int(mid))
            if m is None:
                continue
            series = dict(zip(zip(group["year"], group["epi_week"], strict=True), group["cases"], strict=True))
            y = np.array([series.get(k, 0) for k in weeks], dtype=float)
            df = pd.DataFrame({"municipality_id": int(mid), "year": [a for a, _ in weeks],
                               "epi_week": [s for _, s in weeks], "t_idx": range(len(weeks)), "cases": y})
            log_y = np.log1p(pd.Series(y))
            for k in range(4):
                df[f"y_l{k}"] = log_y.shift(k)
            df["y_ma4"] = np.log1p(pd.Series(y).rolling(4).mean())
            df["y_ma8"] = np.log1p(pd.Series(y).rolling(8).mean())
            df["rate_l0"] = y / m.population * 100_000
            # Same weeks of the previous year as the target weeks (t+1..t+4 → t-51..t-48)
            df["y_prev_year"] = np.log1p(pd.Series(y).shift(48).rolling(4).mean())
            df["week_sin"] = [math.sin(2 * math.pi * s / 52.18) for _, s in weeks]
            df["week_cos"] = [math.cos(2 * math.pi * s / 52.18) for _, s in weeks]

            def column(source: dict, key: Callable, field: str | None = None, lag: int = 0) -> pd.Series:
                values = []
                for y_, w_ in weeks:
                    v = source.get(key(shift(y_, w_, -lag)))
                    values.append(np.nan if v is None else (v.get(field, np.nan) if field else v))
                return pd.Series(values, dtype=float)

            mkey = _municipality_key(int(mid))
            temp, rain, hum = column(weather, mkey, "t"), column(weather, mkey, "p"), column(weather, mkey, "h")
            df["temp_l0"], df["temp_l2"] = temp, temp.shift(2)
            df["temp_l4_6"] = temp.shift(4).rolling(3, min_periods=1).mean()
            df["rain_l0"], df["rain_l1"] = rain, rain.shift(1)
            df["rain_l2_6"] = rain.shift(2).rolling(5, min_periods=2).mean()
            df["hum_l0"], df["hum_l1"] = hum, hum.shift(1)

            s = column(searches, lambda k: k)
            df["search_l0"], df["search_l1"] = s, s.shift(1)
            df["search_change"] = s / s.shift(1).rolling(8, min_periods=4).mean()

            p = column(pharmacy, mkey)
            df["pharm_l0"], df["pharm_l1"] = p, p.shift(1)

            df["so2_l0"] = column(so2, lambda k: k).ffill(limit=4)
            a = column(ash, mkey).fillna(0)
            df["ash_l0_1"] = a.rolling(2, min_periods=1).max()
            df["ash_l2_3"] = a.shift(2).rolling(2, min_periods=1).max()

            df["log_population"] = math.log(m.population)
            df["altitude_km"] = (m.altitude_m or 0) / 1000
            for h in HORIZONS:
                df[f"y_h{h}"] = pd.Series(y).shift(-h)
            blocks.append(df)

        data = pd.concat(blocks, ignore_index=True) if blocks else pd.DataFrame()
        data.attrs["weeks"] = weeks
        data.attrs["week_index"] = week_index
        return data


def trainable_rows(df: pd.DataFrame, h: int) -> pd.DataFrame:
    """Rows with complete lags and a known target for horizon h."""
    return df[df["y_ma8"].notna() & df[f"y_h{h}"].notna()]


def last_row_per_municipality(df: pd.DataFrame) -> pd.DataFrame:
    return df.sort_values("t_idx").groupby("municipality_id").tail(1)
