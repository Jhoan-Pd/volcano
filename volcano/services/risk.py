"""Endemic channel and risk traffic light.

Method: for week W of year Y take the cases of weeks W-1, W and W+1 of the previous 5 years
(up to 15 values) and compute percentiles. With each disease's default thresholds:
    GREEN    cases <= P50           (safety zone)
    YELLOW   P50 < cases <= P75     (alert zone)
    ORANGE   P75 < cases <= P90     (epidemic zone)
    RED      cases > P90            (outbreak: far above what is expected)
The percentiles are configurable per disease from the admin panel.

Minimum floor: with very low counts (e.g. dengue in Pasto, P90 = 0) a single case would trigger
RED, so the level only leaves GREEN with at least MIN_ALERT_CASES cases.
"""
from dataclasses import dataclass

import numpy as np

from volcano.models.enums import RiskLevel
from volcano.shared.epi import EpiWeek, shift, weeks_in_year

HISTORY_YEARS = 5
WEEK_WINDOW = 1
MIN_ALERT_CASES = 3


@dataclass(frozen=True)
class ChannelThresholds:
    yellow: float
    orange: float
    red: float

    def as_dict(self) -> dict[str, float]:
        return {"yellow": self.yellow, "orange": self.orange, "red": self.red}


def reference_weeks(year: int, week: int, years: int = HISTORY_YEARS, window: int = WEEK_WINDOW) -> list[EpiWeek]:
    """Historical (year, week) pairs comparable with the target week."""
    return [shift(y, min(week, weeks_in_year(y)), d)  # years without week 53 use week 52
            for y in range(year - years, year) for d in range(-window, window + 1)]


def compute_thresholds(values: list[float], p_yellow: int, p_orange: int, p_red: int) -> ChannelThresholds | None:
    if len(values) < 3:
        return None
    arr = np.asarray(values, dtype=float)
    y, o, r = np.percentile(arr, [p_yellow, p_orange, p_red])
    return ChannelThresholds(round(float(y), 2), round(float(o), 2), round(float(r), 2))


def classify(cases: float, t: ChannelThresholds | None) -> RiskLevel:
    if t is None or cases < MIN_ALERT_CASES:
        return RiskLevel.GREEN
    if cases > t.red:
        return RiskLevel.RED
    if cases > t.orange:
        return RiskLevel.ORANGE
    if cases > t.yellow:
        return RiskLevel.YELLOW
    return RiskLevel.GREEN
