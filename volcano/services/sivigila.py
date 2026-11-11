"""Official cases: syncs SIVIGILA (datos.gov.co) with the official_cases table.

Rule: an official value replaces the simulated one of the same week. Socrata only publishes weeks
with cases, so for the years the dataset does cover, missing weeks are stored with 0 cases (also as
official data).
"""
import logging
from collections import defaultdict

from volcano.repositories.domain import DiseaseRepository, MunicipalityRepository, OfficialCaseRepository
from volcano.schemas.data_sources import SivigilaSyncResult
from volcano.shared.config import settings
from volcano.shared.epi import weeks_in_year
from volcano.sources import DataSource, DataSourceError, SivigilaSource

logger = logging.getLogger("volcano.sivigila")


class SivigilaService:
    def __init__(self, db, source: DataSource | None = None):
        self.db = db
        self.source = source or SivigilaSource()
        self.cases = OfficialCaseRepository(db)
        self.diseases = DiseaseRepository(db)
        self.municipalities = MunicipalityRepository(db)

    def sync(self, since_year: int | None = None) -> SivigilaSyncResult:
        since_year = since_year or settings.SEED_START_YEAR
        municipalities = {m.divipola_code: m.id for m in self.municipalities.active()}
        codes, all_years, errors = [], set(), []
        saved = with_cases = 0
        for disease in self.diseases.active():
            event_codes = disease.sivigila_code_list
            if not event_codes:
                continue
            codes.append(disease.code)
            try:
                rows = self.source.fetch(event_codes=event_codes, since_year=since_year)
            except (DataSourceError, ValueError) as exc:
                logger.warning("SIVIGILA %s: %s", disease.code, exc)
                errors.append(f"{disease.code}: {exc}")
                continue
            # Covered years = years with at least one row in the department
            years = sorted({r["year"] for r in rows if r["year"] >= since_year})
            totals: dict[tuple[str, int, int], int] = defaultdict(int)
            for r in rows:
                totals[(r["divipola_code"], r["year"], r["epi_week"])] += r["cases"]
            batch = []
            for divipola, mid in municipalities.items():
                for year in years:
                    for week in range(1, weeks_in_year(year) + 1):
                        cases = totals.get((divipola, year, week), 0)
                        with_cases += cases > 0
                        batch.append({"municipality_id": mid, "disease_id": disease.id, "year": year,
                                      "epi_week": week, "cases": cases, "source": self.source.name,
                                      "is_simulated": False})
            inserted, updated = self.cases.upsert_weeks(batch)
            saved += inserted + updated
            all_years.update(years)
        return SivigilaSyncResult(diseases=codes, years_covered=sorted(all_years), saved_rows=saved,
                                  weeks_with_cases=with_cases, errors=errors)
