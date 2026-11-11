"""ORM models. Importing any of them registers every table in Base.metadata (Alembic needs that).

The package loads its submodules lazily (PEP 562): `volcano.models.enums` can be imported without
pulling in SQLAlchemy, which keeps the realtime hub light.
"""
from importlib import import_module
from typing import TYPE_CHECKING, Any

_EXPORTS = {
    "Base": "volcano.db.base",
    "Disease": "volcano.models.catalog", "Municipality": "volcano.models.catalog",
    "Pharmacy": "volcano.models.pharmacy", "PharmacyReport": "volcano.models.pharmacy",
    "Alert": "volcano.models.prediction", "Prediction": "volcano.models.prediction",
    "TrainedModel": "volcano.models.prediction",
    "Role": "volcano.models.security", "User": "volcano.models.security",
    "OfficialCase": "volcano.models.timeseries", "SearchTrend": "volcano.models.timeseries",
    "VolcanicEvent": "volcano.models.timeseries", "WeatherRecord": "volcano.models.timeseries",
}
__all__ = [
    "Alert", "Base", "Disease", "Municipality", "OfficialCase", "Pharmacy", "PharmacyReport", "Prediction",
    "Role", "SearchTrend", "TrainedModel", "User", "VolcanicEvent", "WeatherRecord",
]


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    for module in set(_EXPORTS.values()):  # load every table, not only the one asked for
        import_module(module)
    value = getattr(import_module(_EXPORTS[name]), name)
    globals()[name] = value
    return value


if TYPE_CHECKING:  # static analysers and IDEs see the real names
    from volcano.db.base import Base
    from volcano.models.catalog import Disease, Municipality
    from volcano.models.pharmacy import Pharmacy, PharmacyReport
    from volcano.models.prediction import Alert, Prediction, TrainedModel
    from volcano.models.security import Role, User
    from volcano.models.timeseries import OfficialCase, SearchTrend, VolcanicEvent, WeatherRecord
