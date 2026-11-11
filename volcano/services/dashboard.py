"""Builds the public dashboard from the stored series."""
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import select

from volcano.models import Disease, Municipality, OfficialCase
from volcano.models.enums import RiskLevel
from volcano.repositories.domain import (
    DiseaseRepository,
    MunicipalityRepository,
    OfficialCaseRepository,
    VolcanicEventRepository,
)
from volcano.schemas.dashboard import (
    AshFall,
    DashboardSummary,
    DiseaseRisk,
    DiseaseSeries,
    MunicipalityRisk,
    SeriesPoint,
    Thresholds,
    VolcanoStatus,
)
from volcano.services import risk
from volcano.services.predictions import PredictionQueryService
from volcano.shared.epi import EpiWeek, iter_weeks, label, shift, week_start
from volcano.shared.errors import NotFoundError

Series = dict[EpiWeek, int]  # (year, week) → cases
NO_DATA = "NO_DATA"


class DashboardService:
    def __init__(self, db, predictions: PredictionQueryService | None = None):
        self.db = db
        self.municipalities = MunicipalityRepository(db)
        self.diseases = DiseaseRepository(db)
        self.cases = OfficialCaseRepository(db)
        self.events = VolcanicEventRepository(db)
        self.predictions = predictions or PredictionQueryService(db)
        # Per-request cache: disease → municipality → series, and municipalities with simulated data
        self._series: dict[int, dict[int, Series]] = {}
        self._simulated: dict[int, set[int]] = {}
        self._reference: EpiWeek | None = None

    # ── helpers ──────────────────────────────────────────────────────────────
    def _municipality(self, municipality_id: int | None) -> Municipality:
        if municipality_id is None:
            active = self.municipalities.active()
            if not active:
                raise NotFoundError("No hay municipios cargados. Ejecuta el seed.")
            return active[0]
        m = self.municipalities.get(municipality_id)
        if m is None:
            raise NotFoundError(f"Municipio {municipality_id} no existe")
        return m

    def _series_for(self, municipality_id: int, disease_id: int) -> tuple[Series, bool]:
        """Weekly series of one municipality. The first time a disease is requested the cases of
        ALL municipalities are loaded in a single query."""
        if disease_id not in self._series:
            series: dict[int, Series] = defaultdict(dict)
            simulated: set[int] = set()
            for mid, y, w, c, sim in self.db.execute(
                    select(OfficialCase.municipality_id, OfficialCase.year, OfficialCase.epi_week, OfficialCase.cases,
                           OfficialCase.is_simulated).where(OfficialCase.disease_id == disease_id)):
                series[mid][(y, w)] = c
                if sim:
                    simulated.add(mid)
            self._series[disease_id], self._simulated[disease_id] = dict(series), simulated
        return self._series[disease_id].get(municipality_id, {}), municipality_id in self._simulated[disease_id]

    @staticmethod
    def _thresholds(series: dict, disease: Disease, year: int, week: int) -> risk.ChannelThresholds | None:
        values = [series[p] for p in risk.reference_weeks(year, week) if p in series]
        return risk.compute_thresholds(values, disease.yellow_threshold_pct, disease.orange_threshold_pct,
                                       disease.red_threshold_pct)

    def reference_week(self) -> EpiWeek:
        if self._reference is None:
            self._reference = self.cases.latest_week()
            if self._reference is None:
                raise NotFoundError("No hay casos registrados. Ejecuta el seed.")
        return self._reference

    # ── use cases ────────────────────────────────────────────────────────────
    def disease_risk(self, m: Municipality, disease: Disease, year: int, week: int) -> DiseaseRisk:
        series, simulated = self._series_for(m.id, disease.id)
        cases = series.get((year, week), 0)
        previous = series.get(shift(year, week, -1))
        t = self._thresholds(series, disease, year, week)
        change = round((cases - previous) / previous * 100, 1) if previous else None
        return DiseaseRisk(
            disease_id=disease.id, code=disease.code, name=disease.name, color=disease.color,
            year=year, epi_week=week, cases=cases, previous_week_cases=previous,
            change_pct=change, rate_per_100k=round(cases / m.population * 100_000, 2),
            thresholds=Thresholds(**t.as_dict()) if t else Thresholds(yellow=0, orange=0, red=0),
            level=risk.classify(cases, t).value, is_simulated=simulated,
            recommendations=disease.recommendation_list,
            prediction=self.predictions.summary(m.id, disease.id),
        )

    def volcano_status(self, today: date | None = None) -> VolcanoStatus:
        today = today or date.today()
        b = self.events.latest_bulletin()
        ash_falls = self.events.ash_falls_since(today - timedelta(days=365))[:5]
        return VolcanoStatus(
            activity_level=b.activity_level if b else NO_DATA,
            date=b.start_date if b else None,
            description=b.description if b else None,
            bulletin_url=b.bulletin_url if b else None,
            is_simulated=b.is_simulated if b else True,
            so2_tons_per_day=b.so2_tons_per_day if b else None,
            recent_ash_falls=[
                AshFall(date=e.start_date, municipality=e.municipality.name if e.municipality else None,
                        intensity=e.ash_intensity, description=e.description, is_simulated=e.is_simulated)
                for e in ash_falls
            ],
        )

    def summary(self, municipality_id: int | None) -> DashboardSummary:
        m = self._municipality(municipality_id)
        year, week = self.reference_week()
        risks = [self.disease_risk(m, d, year, week) for d in self.diseases.active()]
        volcano = self.volcano_status()
        return DashboardSummary(
            municipality_id=m.id, municipality=m.name, population=m.population,
            reference_week=label(year, week), risks=risks, volcano=volcano,
            has_simulated_data=any(r.is_simulated for r in risks) or volcano.is_simulated,
        )

    def series(self, municipality_id: int, disease_id: int, weeks: int = 104) -> DiseaseSeries:
        m = self._municipality(municipality_id)
        disease = self.diseases.get(disease_id)
        if disease is None:
            raise NotFoundError(f"Enfermedad {disease_id} no existe")
        series, _ = self._series_for(m.id, disease.id)
        end = self.reference_week()
        points = []
        for y, w in iter_weeks(shift(*end, -(weeks - 1)), end):
            t = self._thresholds(series, disease, y, w)
            points.append(SeriesPoint(
                year=y, epi_week=w, label=label(y, w), week_start=week_start(y, w), cases=series.get((y, w)),
                p_yellow=t.yellow if t else None, p_orange=t.orange if t else None, p_red=t.red if t else None,
            ))
        return DiseaseSeries(municipality_id=m.id, disease_id=disease.id, disease=disease.name, points=points)

    def risk_by_municipality(self) -> list[MunicipalityRisk]:
        year, week = self.reference_week()
        diseases = self.diseases.active()
        out = []
        for m in self.municipalities.active():
            risks = [self.disease_risk(m, d, year, week) for d in diseases]
            levels = {r.code: r.level for r in risks}
            predicted = {r.code: r.prediction.max_level for r in risks if r.prediction}
            out.append(MunicipalityRisk(
                municipality_id=m.id, municipality=m.name, divipola_code=m.divipola_code,
                latitude=m.latitude, longitude=m.longitude,
                max_level=RiskLevel.worst(levels.values()).value, levels=levels,
                max_predicted_level=RiskLevel.worst(predicted.values()).value if predicted else None,
                predicted_levels=predicted,
            ))
        return out
