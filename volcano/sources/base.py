"""Abstraction over external data sources.

Strategy + Adapter:
- Strategy: services depend on the `DataSource` interface, not on a concrete API, so Open-Meteo
  could be swapped for IDEAM, or pytrends for a CSV, without touching the service.
- Adapter: each implementation turns the source's own format (Open-Meteo JSON, a pytrends
  DataFrame, Socrata JSON) into a list of dicts with the columns of OUR tables.

Implementations:
    OpenMeteoSource  -> weather_records
    TrendsSource     -> search_trends
    SivigilaSource   -> official_cases
    PharmacySource   -> sales index computed from pharmacy_reports
"""
import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger("volcano.sources")


class DataSourceError(Exception):
    """The external source did not answer or returned invalid data."""


class DataSource(ABC):
    #: Short name stored in the `source` column of every row
    name: str = "unknown"

    @abstractmethod
    def fetch(self, **params: Any) -> list[dict[str, Any]]:
        """Download the data and return it normalized (a list of rows ready for the database)."""

    def available(self) -> bool:
        """Quick health check; by default it tries a minimal request."""
        try:
            self.check()
            return True
        except Exception as exc:
            logger.warning("Source %s unavailable: %s", self.name, exc)
            return False

    def check(self) -> None:  # pragma: no cover - subclasses override it
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"
