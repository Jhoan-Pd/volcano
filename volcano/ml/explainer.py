"""Local explanations: "why did the risk go up?".

Group occlusion: for one prediction, the features of a group (e.g. "searches") are replaced
with their typical value (the historical median) and the model predicts again. The difference
is the group's contribution, in cases:

    contribution(group) = actual prediction − prediction with the group at its typical value

It is easier to explain than SHAP and needs no extra library. Readable Spanish sentences are
generated from the observed values as well (searches +40 %, recent ash fall, etc.).
"""
import math

import numpy as np
import pandas as pd

from volcano.ml.features import FEATURE_GROUPS
from volcano.models.enums import ProductCategory
from volcano.shared.text import format_number_es


def contributions(model, x: pd.DataFrame, medians: dict) -> tuple[float, dict[str, float]]:
    base = float(model.predict(x)[0])
    out = {}
    for group, features in FEATURE_GROUPS.items():
        x2 = x.copy()
        for f in features:
            x2[f] = np.nan if medians.get(f) is None else medians[f]
        out[group] = round(base - float(model.predict(x2)[0]), 2)
    return base, out


def _pct(v: float) -> str:
    return f"{'+' if v >= 0 else '−'}{abs(v):.0f} %"


def _ok(v) -> bool:
    return v is not None and not (isinstance(v, float) and math.isnan(v))


def _category_label(code: str) -> str:
    try:
        return ProductCategory(code).label_es
    except ValueError:
        return code.lower()


def signals(row: pd.Series, medians: dict, terms: list[str], categories: list[str]) -> dict[str, str]:
    """Spanish sentences describing what each feature group shows in the current week."""
    m: dict[str, str] = {}
    if _ok(row.get("y_l0")) and _ok(row.get("y_ma8")):
        current, mean = math.expm1(row["y_l0"]), math.expm1(row["y_ma8"])
        if mean > 0.5:
            change = (current / mean - 1) * 100
            m["recent_cases"] = (f"Los casos de la última semana ({current:.0f}) están {_pct(change)} frente al "
                                 f"promedio de las 8 semanas anteriores ({format_number_es(mean)}).")
    if _ok(row.get("search_change")):
        change = (row["search_change"] - 1) * 100
        m["searches"] = (f"Las búsquedas en internet de «{', '.join(terms)}» en Nariño están "
                         f"{_pct(change)} respecto a su nivel habitual.")
    if _ok(row.get("pharm_l0")):
        change = row["pharm_l0"] - 100
        names = ", ".join(_category_label(c) for c in categories) or "productos asociados"
        m["pharmacy"] = f"Las ventas de {names} en las farmacias del municipio están {_pct(change)} de lo normal."
    parts = []
    if _ok(row.get("rain_l2_6")) and _ok(medians.get("rain_l2_6")) and medians["rain_l2_6"] > 0:
        rain_change = (row["rain_l2_6"] / medians["rain_l2_6"] - 1) * 100
        parts.append(f"lluvia de las semanas previas {_pct(rain_change)}")
    if _ok(row.get("temp_l0")) and _ok(medians.get("temp_l0")):
        parts.append(f"temperatura {'+' if row['temp_l0'] >= medians['temp_l0'] else '−'}"
                     f"{format_number_es(abs(row['temp_l0'] - medians['temp_l0']))} °C")
    if parts:
        m["weather"] = "Frente a lo típico: " + ", ".join(parts) + "."
    if _ok(row.get("ash_l0_1")) and row["ash_l0_1"] > 0:
        m["volcano"] = f"Hubo caída de ceniza reciente en el municipio (intensidad {int(row['ash_l0_1'])} de 3)."
    elif _ok(row.get("so2_l0")) and _ok(medians.get("so2_l0")) and medians["so2_l0"]:
        change = (row["so2_l0"] / medians["so2_l0"] - 1) * 100
        if abs(change) >= 25:
            m["volcano"] = f"La emisión de SO₂ del Galeras está {_pct(change)} frente a su mediana."
    if _ok(row.get("y_prev_year")):
        m["seasonality"] = (f"En estas mismas semanas del año pasado hubo en promedio "
                            f"{format_number_es(math.expm1(row['y_prev_year']))} casos por semana.")
    return m


def explain(model, x: pd.DataFrame, row: pd.Series, medians: dict, terms: list[str],
            categories: list[str]) -> dict:
    base, contrib = contributions(model, x, medians)
    sentences = signals(row, medians, terms, categories)
    factors = [
        {"group": g, "contribution": c, "direction": "up" if c > 0 else "down" if c < 0 else "neutral",
         "message": sentences.get(g)}
        for g, c in sorted(contrib.items(), key=lambda kv: -abs(kv[1]))
    ]
    return {"method": "group occlusion (typical value = historical median)", "prediction": round(base, 2),
            "factors": factors}
