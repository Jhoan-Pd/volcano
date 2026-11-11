"""SIVIGILA (INS) adapter, published on datos.gov.co through the Socrata API (SODA).

Dataset `4hyg-wa9d` "Datos de Vigilancia en Salud Pública de Colombia". Columns used:
    cod_eve      INS event code (210 dengue, 220 severe dengue, 345/348 SARI…)
    cod_dpto_o   department where it happened (52 = Nariño)
    cod_mun_o    municipality where it happened (5-digit DIVIPOLA)
    ano, semana  year and epidemiological week
    conteo       cases that week

Known limitations (documented for the defence):
- The dataset ends in 2022 (last updated Oct 2024).
- It only lists weeks with cases: missing weeks of a covered year are 0.
- IRA and EDA morbidity (collective events 995/998) is NOT in this dataset, so those diseases keep
  simulated data and the mapping is configurable per disease.

The aggregation runs on the Socrata server ($select + $group) so only a few rows are downloaded,
and $limit/$offset paginate in case the query grows.
"""
from typing import Any

import httpx

from volcano.shared.config import settings
from volcano.sources.base import DataSource, DataSourceError, logger
from volcano.sources.http import get_json

PAGE_SIZE = 50_000


class SivigilaSource(DataSource):
    name = "SIVIGILA (datos.gov.co)"

    def __init__(self, client: httpx.Client | None = None, url: str | None = None, app_token: str | None = None,
                 timeout: float | None = None):
        self._client = client
        self.url = url or settings.SOCRATA_URL
        self.app_token = app_token if app_token is not None else settings.SOCRATA_APP_TOKEN
        self._timeout = timeout or max(settings.HTTP_TIMEOUT_SECONDS, 40)

    def _get(self, params: dict[str, Any], retries: int = 2) -> list[dict[str, Any]]:
        headers = {"X-App-Token": self.app_token} if self.app_token else None
        data = get_json(self.url, params, client=self._client, timeout=self._timeout, headers=headers,
                        retries=retries, backoff_s=1.0, source="datos.gov.co")
        if not isinstance(data, list):
            raise DataSourceError("Unexpected Socrata response format")
        return data

    @staticmethod
    def build_query(event_codes: list[str], department_code: str, since_year: int) -> dict[str, str]:
        if not event_codes or not all(c.isdigit() for c in event_codes):
            raise ValueError("Event codes must be numeric")
        codes = ",".join(f"'{c}'" for c in event_codes)
        return {
            "$select": "cod_eve,cod_mun_o,ano,semana,sum(conteo) as casos",
            "$where": f"cod_dpto_o='{int(department_code)}' AND cod_eve in({codes}) AND ano >= '{int(since_year)}'",
            "$group": "cod_eve,cod_mun_o,ano,semana",
            "$order": "ano,semana,cod_mun_o",
        }

    @staticmethod
    def adapt(row: dict[str, Any]) -> dict[str, Any] | None:
        try:
            return {
                "event_code": str(row["cod_eve"]).strip(),
                "divipola_code": str(int(float(row["cod_mun_o"]))).zfill(5),
                "year": int(float(row["ano"])),
                "epi_week": int(float(row["semana"])),
                "cases": round(float(row.get("casos", row.get("sum_conteo", 0)) or 0)),
            }
        except (KeyError, TypeError, ValueError):
            return None  # incomplete row: dropped

    def fetch(self, *, event_codes: list[str], department_code: str | None = None,
              since_year: int = 2020, **_: Any) -> list[dict[str, Any]]:
        """Cases per (event, municipality, year, week) for the whole department."""
        params = self.build_query(event_codes, department_code or settings.SIVIGILA_DEPARTMENT, since_year)
        rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            page = self._get({**params, "$limit": PAGE_SIZE, "$offset": offset})
            rows += [r for r in (self.adapt(x) for x in page) if r is not None and 1 <= r["epi_week"] <= 53]
            if len(page) < PAGE_SIZE:
                break
            offset += PAGE_SIZE
        logger.info("SIVIGILA events %s: %d rows", ",".join(event_codes), len(rows))
        return rows

    def check(self) -> None:  # pragma: no cover - network
        self._get({"$select": "count(*)", "$where": "cod_dpto_o='52'", "$limit": 1})
