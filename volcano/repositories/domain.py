"""Concrete repositories, one per entity."""
from datetime import date

from sqlalchemy import and_, or_, select

from volcano.models import (
    Disease,
    Municipality,
    OfficialCase,
    Pharmacy,
    Role,
    SearchTrend,
    User,
    VolcanicEvent,
    WeatherRecord,
)
from volcano.models.enums import VolcanicEventType
from volcano.repositories.base import BaseRepository
from volcano.shared.epi import EpiWeek


class RoleRepository(BaseRepository[Role]):
    model = Role

    def by_name(self, name: str) -> Role | None:
        return self.get_by(name=name)


class UserRepository(BaseRepository[User]):
    model = User

    def by_email(self, email: str) -> User | None:
        return self.db.scalars(select(User).where(User.email == email.lower())).first()


class MunicipalityRepository(BaseRepository[Municipality]):
    model = Municipality

    def active(self) -> list[Municipality]:
        return list(self.db.scalars(select(Municipality).where(Municipality.active.is_(True))
                                    .order_by(Municipality.id)))


class DiseaseRepository(BaseRepository[Disease]):
    model = Disease

    def active(self) -> list[Disease]:
        return list(self.db.scalars(select(Disease).where(Disease.active.is_(True)).order_by(Disease.id)))


class PharmacyRepository(BaseRepository[Pharmacy]):
    model = Pharmacy


class VolcanicEventRepository(BaseRepository[VolcanicEvent]):
    model = VolcanicEvent

    def latest_bulletin(self) -> VolcanicEvent | None:
        stmt = (select(VolcanicEvent).where(VolcanicEvent.event_type == VolcanicEventType.BULLETIN)
                .order_by(VolcanicEvent.start_date.desc(), VolcanicEvent.id.desc()).limit(1))
        return self.db.scalars(stmt).first()

    def ash_falls_since(self, since: date, municipality_id: int | None = None) -> list[VolcanicEvent]:
        stmt = select(VolcanicEvent).where(
            VolcanicEvent.event_type == VolcanicEventType.ASH_FALL, VolcanicEvent.start_date >= since
        )
        if municipality_id:
            stmt = stmt.where(VolcanicEvent.municipality_id == municipality_id)
        return list(self.db.scalars(stmt.order_by(VolcanicEvent.start_date.desc())).unique())


class WeatherRecordRepository(BaseRepository[WeatherRecord]):
    model = WeatherRecord

    def between(self, municipality_id: int, since: date, until: date | None = None) -> list[WeatherRecord]:
        stmt = select(WeatherRecord).where(WeatherRecord.municipality_id == municipality_id,
                                           WeatherRecord.date >= since)
        if until:
            stmt = stmt.where(WeatherRecord.date <= until)
        return list(self.db.scalars(stmt.order_by(WeatherRecord.date)))

    def latest_observed(self, municipality_id: int) -> WeatherRecord | None:
        stmt = (select(WeatherRecord)
                .where(WeatherRecord.municipality_id == municipality_id, WeatherRecord.is_forecast.is_(False))
                .order_by(WeatherRecord.date.desc()).limit(1))
        return self.db.scalars(stmt).first()

    def upsert_days(self, municipality_id: int, rows: list[dict]) -> int:
        """Insert or update a municipality's days by (municipality_id, date). Returns how many were saved."""
        rows = [{**r, "municipality_id": municipality_id} for r in rows]
        inserted, updated = self.upsert(rows, ("municipality_id", "date"), [
            WeatherRecord.municipality_id == municipality_id, WeatherRecord.date.in_([r["date"] for r in rows])])
        return inserted + updated


class OfficialCaseRepository(BaseRepository[OfficialCase]):
    model = OfficialCase

    def series(self, municipality_id: int, disease_id: int) -> list[OfficialCase]:
        stmt = (select(OfficialCase)
                .where(OfficialCase.municipality_id == municipality_id, OfficialCase.disease_id == disease_id)
                .order_by(OfficialCase.year, OfficialCase.epi_week))
        return list(self.db.scalars(stmt))

    def latest_week(self) -> EpiWeek | None:
        stmt = select(OfficialCase.year, OfficialCase.epi_week).order_by(
            OfficialCase.year.desc(), OfficialCase.epi_week.desc()).limit(1)
        row = self.db.execute(stmt).first()
        return (row[0], row[1]) if row else None

    def upsert_weeks(self, rows: list[dict]) -> tuple[int, int]:
        """Insert or update by (municipality, disease, year, week). Returns (inserted, updated)."""
        return self.upsert(rows, ("municipality_id", "disease_id", "year", "epi_week"), [
            OfficialCase.municipality_id.in_({r["municipality_id"] for r in rows}),
            OfficialCase.disease_id.in_({r["disease_id"] for r in rows}),
            OfficialCase.year.in_({r["year"] for r in rows}),
        ])

    def weeks(self, municipality_id: int, disease_id: int, pairs: list[EpiWeek]) -> list[OfficialCase]:
        if not pairs:
            return []
        cond = or_(*[and_(OfficialCase.year == y, OfficialCase.epi_week == w) for y, w in pairs])
        stmt = select(OfficialCase).where(
            OfficialCase.municipality_id == municipality_id, OfficialCase.disease_id == disease_id, cond)
        return list(self.db.scalars(stmt))


class SearchTrendRepository(BaseRepository[SearchTrend]):
    model = SearchTrend

    def series(self, term: str, region: str, since: date | None = None) -> list[SearchTrend]:
        stmt = select(SearchTrend).where(SearchTrend.term == term, SearchTrend.region == region)
        if since:
            stmt = stmt.where(SearchTrend.week_start >= since)
        return list(self.db.scalars(stmt.order_by(SearchTrend.week_start)))

    def latest_real(self, term: str, region: str) -> SearchTrend | None:
        """Most recent row that came from a real source (pytrends or CSV), not simulated."""
        stmt = (select(SearchTrend)
                .where(SearchTrend.term == term, SearchTrend.region == region, SearchTrend.is_simulated.is_(False))
                .order_by(SearchTrend.week_start.desc()).limit(1))
        return self.db.scalars(stmt).first()

    def upsert_weeks(self, rows: list[dict]) -> int:
        """Insert or update by (term, region, year, epi_week). Returns how many were saved."""
        inserted, updated = self.upsert(rows, ("term", "region", "year", "epi_week"),
                                        [SearchTrend.term.in_({r["term"] for r in rows})])
        return inserted + updated
