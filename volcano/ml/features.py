"""Feature catalogue of the model: names, groups and the Spanish labels of the groups.

Kept apart from `dataset` (which needs pandas) so the gateway can label explanations without loading
the data-science stack.
"""

HORIZONS = (1, 2, 3, 4)

FEATURE_GROUPS: dict[str, list[str]] = {
    "recent_cases": ["y_l0", "y_l1", "y_l2", "y_l3", "y_ma4", "y_ma8", "rate_l0"],
    "seasonality": ["y_prev_year", "week_sin", "week_cos"],
    "weather": ["temp_l0", "temp_l2", "temp_l4_6", "rain_l0", "rain_l1", "rain_l2_6", "hum_l0", "hum_l1"],
    "searches": ["search_l0", "search_l1", "search_change"],
    "pharmacy": ["pharm_l0", "pharm_l1"],
    "volcano": ["so2_l0", "ash_l0_1", "ash_l2_3"],
    "municipality": ["log_population", "altitude_km"],
}
# Spanish names of the groups, as the explanations show them in the UI
GROUP_LABELS_ES: dict[str, str] = {
    "recent_cases": "Casos recientes",
    "seasonality": "Estacionalidad",
    "weather": "Clima",
    "searches": "Búsquedas en internet",
    "pharmacy": "Ventas en farmacias",
    "volcano": "Actividad volcánica",
    "municipality": "Municipio",
}
FEATURES: list[str] = [f for fs in FEATURE_GROUPS.values() for f in fs]
TARGETS = [f"y_h{h}" for h in HORIZONS]


def group_of(feature: str) -> str:
    return next(g for g, fs in FEATURE_GROUPS.items() if feature in fs)
