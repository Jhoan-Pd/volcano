"""What-if scenarios: change last week's signals and predict again.

The simulator retrains nothing: it takes the features the model sees today in a municipality,
changes those of one group (weather, searches, pharmacies, volcano) and applies the same model
again. It shows what the forecast is sensitive to; it does not forecast the weather.

Empty features (for example weeks without pharmacy reports) are filled with the municipality's
typical value before applying the change; otherwise "+50 % sales" would have no effect.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

TEMPERATURE = ("temp_l0", "temp_l2", "temp_l4_6")
RAIN = ("rain_l0", "rain_l1", "rain_l2_6")
SEARCHES = ("search_l0", "search_change")  # only the current week moves against its usual level
PHARMACY = ("pharm_l0",)
ASH = "ash_l0_1"
MODERATE_ASH = 2  # bulletin scale: 0 none … 3 heavy

LIMITS = {
    "temperature_delta_c": (-5.0, 5.0),
    "rain_change_pct": (-100.0, 200.0),
    "search_change_pct": (-100.0, 300.0),
    "pharmacy_change_pct": (-100.0, 300.0),
}


@dataclass(frozen=True)
class Adjustments:
    temperature_delta_c: float = 0.0
    rain_change_pct: float = 0.0
    search_change_pct: float = 0.0
    pharmacy_change_pct: float = 0.0
    ash_fall: bool = False

    def errors(self) -> list[str]:
        out = []
        for field, (low, high) in LIMITS.items():
            value = getattr(self, field)
            if not np.isfinite(value) or not low <= value <= high:
                out.append(f"{field} debe estar entre {low:g} y {high:g} (llegó {value:g})")
        return out

    @property
    def unchanged(self) -> bool:
        return self == Adjustments()

    def describe_es(self) -> str:
        """Spanish summary of the changes, used in the simulator result."""
        parts = []
        if self.temperature_delta_c:
            parts.append(f"{self.temperature_delta_c:+.1f} °C".replace(".", ","))
        for field, noun in (("rain_change_pct", "lluvia"), ("search_change_pct", "búsquedas"),
                            ("pharmacy_change_pct", "ventas en farmacias")):
            if getattr(self, field):
                parts.append(f"{getattr(self, field):+.0f} % de {noun}")
        if self.ash_fall:
            parts.append("caída de ceniza")
        return ", ".join(parts) or "sin cambios"


def apply(X: pd.DataFrame, adjustments: Adjustments, typical: dict[str, float | None]) -> pd.DataFrame:
    """Copy of `X` (one row) with the adjustments applied. The input is not modified."""
    X2 = X.copy()

    def base(col: str) -> pd.Series:
        value = typical.get(col)
        return X2[col].fillna(np.nan if value is None else value)

    if adjustments.temperature_delta_c:
        for col in TEMPERATURE:
            X2[col] = base(col) + adjustments.temperature_delta_c
    for cols, pct in ((RAIN, adjustments.rain_change_pct), (SEARCHES, adjustments.search_change_pct),
                      (PHARMACY, adjustments.pharmacy_change_pct)):
        if pct:
            for col in cols:
                X2[col] = (base(col) * (1 + pct / 100)).clip(lower=0)
    if adjustments.ash_fall:
        X2[ASH] = np.maximum(X2[ASH].fillna(0), MODERATE_ASH)
    return X2
