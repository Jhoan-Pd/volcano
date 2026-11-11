"""Symptom searches: syncs Google Trends with the database cache and builds per-disease indexes."""
import logging
from collections import defaultdict
from datetime import date, timedelta

from volcano.models import Disease
from volcano.repositories.domain import DiseaseRepository, SearchTrendRepository
from volcano.schemas.data_sources import TrendPoint, TrendSeries, TrendSyncResult
from volcano.shared.config import settings
from volcano.shared.epi import EpiWeek, label, last_complete_week, week_start
from volcano.sources import DataSource, DataSourceError
from volcano.sources.trends import TrendsSource

logger = logging.getLogger("volcano.trends")


class SearchTrendService:
    def __init__(self, db, source: DataSource | None = None, region: str | None = None):
        self.db = db
        self.source = source or TrendsSource()
        self.region = region or settings.TRENDS_REGION
        self.repo = SearchTrendRepository(db)
        self.diseases = DiseaseRepository(db)

    def terms(self) -> list[str]:
        """Terms of every active disease, without repeats and in order of appearance."""
        return list(dict.fromkeys(t for d in self.diseases.active() for t in d.search_term_list))

    def _is_up_to_date(self, term: str) -> bool:
        latest = self.repo.latest_real(term, self.region)
        if latest is None:
            return False
        return latest.week_start >= week_start(*last_complete_week()) - timedelta(days=7)

    def sync(self, force: bool = False, since: date | None = None) -> TrendSyncResult:
        """Cache first: only queries the terms without real data for the last week."""
        terms = self.terms()
        fresh = [] if force else [t for t in terms if self._is_up_to_date(t)]
        pending = [t for t in terms if t not in fresh]
        if not pending:
            return TrendSyncResult(source="cache", terms=terms, saved_rows=0, from_cache=fresh, errors=[])
        since = since or date(settings.SEED_START_YEAR, 1, 1) - timedelta(days=56)
        try:
            rows = self.source.fetch(terms=pending, region=self.region, since=since)
        except DataSourceError as exc:
            logger.warning("Trends returned no new data: %s", exc)
            return TrendSyncResult(source="cache", terms=terms, saved_rows=0, from_cache=terms, errors=[str(exc)])
        saved = self.repo.upsert_weeks(rows)
        return TrendSyncResult(
            source=getattr(self.source, "last_source", None) or self.source.name, terms=terms,
            saved_rows=saved, from_cache=fresh, errors=[],
        )

    def series(self, term: str, weeks: int = 104) -> TrendSeries:
        since = week_start(*last_complete_week()) - timedelta(weeks=weeks)
        points = [
            TrendPoint(year=t.year, epi_week=t.epi_week, label=label(t.year, t.epi_week), week_start=t.week_start,
                       interest=t.interest, source=t.source, is_simulated=t.is_simulated)
            for t in self.repo.series(term.lower(), self.region, since)
        ]
        return TrendSeries(term=term.lower(), region=self.region, points=points)

    def weekly_interest(self, disease: Disease, since: date | None = None) -> dict[EpiWeek, float]:
        """Weekly mean interest of every search term associated with the disease."""
        acc: dict[EpiWeek, list[float]] = defaultdict(list)
        for term in disease.search_term_list:
            for t in self.repo.series(term, self.region, since):
                acc[(t.year, t.epi_week)].append(t.interest)
        return {k: sum(v) / len(v) for k, v in acc.items()}
