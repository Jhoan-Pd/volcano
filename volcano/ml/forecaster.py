"""Apply a trained model to the last known week of each municipality.

The same logic serves two callers:

- the prediction writer, which stores the weekly predictions in the database;
- the gRPC engine, which keeps the model in memory and answers forecasts and what-if scenarios
  without touching the database.

`Forecaster` runs no queries: it receives the already built dataset and the already deserialized
artifact and only computes (a pure function of its inputs).
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from volcano.ml.dataset import last_row_per_municipality
from volcano.ml.features import FEATURES, HORIZONS
from volcano.models.enums import RiskLevel
from volcano.services import risk
from volcano.shared.epi import EpiWeek, shift


@dataclass(frozen=True)
class ForecastPoint:
    year: int
    epi_week: int
    horizon: int
    expected_cases: float
    lower_bound: float
    upper_bound: float
    level: RiskLevel
    thresholds: risk.ChannelThresholds | None


class Forecaster:
    """1-4 week forecasts of one disease, for every municipality in the dataset."""

    def __init__(self, disease, artifact: dict, df: pd.DataFrame):
        self.disease = disease
        self.artifact = artifact
        self._last_rows: dict[int, pd.Series] = {}
        self._series: dict[int, dict[EpiWeek, float]] = {}
        self._typical: dict[int, dict[str, float | None]] = {}
        if df.empty:
            return
        self._last_rows = {int(r["municipality_id"]): r for _, r in last_row_per_municipality(df).iterrows()}
        medians = artifact["medians"]
        for key, group in df.groupby("municipality_id"):
            mid = int(key)
            self._series[mid] = {(int(y), int(w)): c for y, w, c in
                                 group[["year", "epi_week", "cases"]].itertuples(index=False)}
            # The municipality's own "typical value" (Pasto at 2,527 m is not Consacá at 1,730 m)
            self._typical[mid] = {f: (medians.get(f) if pd.isna(v) else float(v))
                                  for f, v in group[FEATURES].median().items()}

    # ── inputs ───────────────────────────────────────────────────────────────
    def municipalities(self) -> list[int]:
        return sorted(self._last_rows)

    def has(self, municipality_id: int) -> bool:
        return municipality_id in self._last_rows

    def row(self, municipality_id: int) -> pd.Series:
        """Features of the last week with data (what is known today)."""
        return self._last_rows[municipality_id]

    def inputs(self, municipality_id: int) -> pd.DataFrame:
        row = self._last_rows[municipality_id]
        return pd.DataFrame([row[FEATURES].astype(float)], columns=FEATURES)

    def typical(self, municipality_id: int) -> dict[str, float | None]:
        return self._typical[municipality_id]

    def base_week(self, municipality_id: int) -> EpiWeek:
        row = self._last_rows[municipality_id]
        return int(row["year"]), int(row["epi_week"])

    def estimator(self, horizon: int):
        return self.artifact["models"][horizon]

    # ── computation ──────────────────────────────────────────────────────────
    def thresholds(self, municipality_id: int, year: int, week: int) -> risk.ChannelThresholds | None:
        series = self._series.get(municipality_id, {})
        d = self.disease
        return risk.compute_thresholds([series[p] for p in risk.reference_weeks(year, week) if p in series],
                                       d.yellow_threshold_pct, d.orange_threshold_pct, d.red_threshold_pct)

    def forecast(self, municipality_id: int, X: pd.DataFrame | None = None) -> list[ForecastPoint]:
        """Forecast of the coming weeks. `X` lets callers pass modified features (a scenario);
        when omitted the features of the last observed week are used."""
        if X is None:
            X = self.inputs(municipality_id)
        year, week = self.base_week(municipality_id)
        points = []
        for h in HORIZONS:
            p_log = float(self.estimator(h).predict_log(X)[0])
            q10, q90 = self.artifact["quantiles"][str(h)]
            expected = max(float(np.expm1(p_log)), 0.0)
            y, w = shift(year, week, h)
            t = self.thresholds(municipality_id, y, w)
            points.append(ForecastPoint(
                year=y, epi_week=w, horizon=h, expected_cases=round(expected, 2),
                lower_bound=round(max(float(np.expm1(p_log + q10)), 0.0), 2),
                upper_bound=round(max(float(np.expm1(p_log + q90)), 0.0), 2),
                level=risk.classify(expected, t), thresholds=t))
        return points
