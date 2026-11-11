"""Read side of the predictions: what the dashboard, alerts and reports show.

Writing predictions (training, applying the models) needs scikit-learn and lives in
`volcano.services.forecasting`, which only the engine imports. Keeping this module free of the
ML stack keeps the gateway light.
"""
from collections import defaultdict

from sqlalchemy import select

from volcano.ml.features import GROUP_LABELS_ES
from volcano.models import Disease, Municipality, Prediction, TrainedModel
from volcano.models.enums import RiskLevel
from volcano.repositories.domain import DiseaseRepository
from volcano.schemas.dashboard import Thresholds
from volcano.schemas.model import (
    BacktestPoint,
    DiseasePrediction,
    ExplanationFactor,
    ModelOut,
    ModelSummary,
    PredictionExplanation,
    PredictionPoint,
    PredictionSummary,
)
from volcano.shared.epi import EpiWeek, label, shift, week_start
from volcano.shared.errors import NotFoundError
from volcano.shared.text import format_number_es


def model_out(m: TrainedModel, disease_code: str) -> ModelOut:
    improvement = None
    if m.baseline_mae and m.model_mae is not None:
        improvement = round((1 - m.model_mae / m.baseline_mae) * 100, 1)
    return ModelOut(
        id=m.id, disease_id=m.disease_id, disease=disease_code, algorithm=m.algorithm, version=m.version,
        trained_at=m.trained_at, baseline_mae=m.baseline_mae, baseline_rmse=m.baseline_rmse, model_mae=m.model_mae,
        model_rmse=m.model_rmse, mae_improvement_pct=improvement, sample_count=m.sample_count, active=m.active,
        importances=m.importances, metrics=(m.parameters or {}).get("metrics"),
    )


def _peak(predictions: list[Prediction]) -> Prediction:
    return max(predictions, key=lambda p: (RiskLevel(p.risk_level).rank, p.expected_cases))


class PredictionQueryService:
    """Lives for one request: keeps each disease's active model and its predictions grouped by
    municipality, so the dashboard, alerts and reports (asking for 6 municipalities × 4 diseases)
    do not repeat the same query."""

    def __init__(self, db):
        self.db = db
        self.diseases = DiseaseRepository(db)
        self._models: dict[int, TrainedModel | None] = {}
        self._current: dict[int, dict[int, list[Prediction]]] = {}  # model → municipality → predictions

    def clear_cache(self) -> None:
        self._models.clear()
        self._current.clear()

    def active_model(self, disease_id: int) -> TrainedModel | None:
        if disease_id not in self._models:
            self._models[disease_id] = self.db.scalars(select(TrainedModel).where(
                TrainedModel.disease_id == disease_id, TrainedModel.active.is_(True))
                .order_by(TrainedModel.id.desc()).limit(1)).first()
        return self._models[disease_id]

    def latest_predictions(self, model_id: int, municipality_id: int) -> list[Prediction]:
        """Predictions of the most recent run (horizons 1-4) of a model for one municipality.

        The first call for a model loads ALL its predictions in one query and groups them by
        municipality; the following ones are a dictionary lookup (O(1))."""
        if model_id not in self._current:
            by_municipality: dict[int, list[Prediction]] = defaultdict(list)
            for p in self.db.scalars(select(Prediction).where(Prediction.model_id == model_id)):
                by_municipality[p.municipality_id].append(p)
            self._current[model_id] = {mid: self._latest_run(ps) for mid, ps in by_municipality.items()}
        return self._current[model_id].get(municipality_id, [])

    @staticmethod
    def _latest_run(predictions: list[Prediction]) -> list[Prediction]:
        """Of several weekly runs, only the latest (same origin week), sorted by horizon."""
        def origin(p: Prediction) -> EpiWeek:
            return shift(p.year, p.epi_week, -p.horizon)
        latest = max(map(origin, predictions))
        return sorted((p for p in predictions if origin(p) == latest), key=lambda p: p.horizon)

    def _disease(self, disease_id: int) -> Disease:
        d = self.diseases.get(disease_id)
        if d is None:
            raise NotFoundError(f"Enfermedad {disease_id} no existe")
        return d

    def prediction(self, municipality_id: int, disease_id: int) -> DiseasePrediction:
        disease = self._disease(disease_id)
        m = self.active_model(disease.id)
        if m is None:
            return DiseasePrediction(municipality_id=municipality_id, disease_id=disease.id, disease=disease.name,
                                     base_week=None, model=None, max_level=None, points=[], backtest=[])
        preds = self.latest_predictions(m.id, municipality_id)
        points = []
        for p in preds:
            t = (p.explanation or {}).get("thresholds")
            points.append(PredictionPoint(
                year=p.year, epi_week=p.epi_week, label=label(p.year, p.epi_week),
                week_start=week_start(p.year, p.epi_week), horizon=p.horizon, expected_cases=p.expected_cases,
                lower_bound=p.lower_bound, upper_bound=p.upper_bound, level=p.risk_level,
                thresholds=Thresholds(**t) if t else None))
        backtest = [BacktestPoint(year=b["year"], epi_week=b["epi_week"], label=label(b["year"], b["epi_week"]),
                                  observed=b["observed"], predicted=b["predicted"])
                    for b in (m.parameters or {}).get("backtest", []) if b["municipality_id"] == municipality_id]
        base = shift(preds[0].year, preds[0].epi_week, -1) if preds else None
        return DiseasePrediction(
            municipality_id=municipality_id, disease_id=disease.id, disease=disease.name,
            base_week=label(*base) if base else None,
            model=ModelSummary(id=m.id, algorithm=m.algorithm, trained_at=m.trained_at, baseline_mae=m.baseline_mae,
                               model_mae=m.model_mae, baseline_rmse=m.baseline_rmse, model_rmse=m.model_rmse),
            max_level=RiskLevel.worst(p.level for p in points).value if points else None,
            points=points, backtest=backtest)

    def summary(self, municipality_id: int, disease_id: int) -> PredictionSummary | None:
        m = self.active_model(disease_id)
        if m is None:
            return None
        preds = self.latest_predictions(m.id, municipality_id)
        if not preds:
            return None
        peak, h1 = _peak(preds), preds[0]
        return PredictionSummary(max_level=peak.risk_level, peak_week=label(peak.year, peak.epi_week),
                                 expected_cases_h1=h1.expected_cases, lower_bound_h1=h1.lower_bound,
                                 upper_bound_h1=h1.upper_bound, algorithm=m.algorithm)

    def explanation(self, municipality_id: int, disease_id: int, horizon: int | None = None) -> PredictionExplanation:
        disease = self._disease(disease_id)
        municipality = self.db.get(Municipality, municipality_id)
        if municipality is None:
            raise NotFoundError(f"Municipio {municipality_id} no existe")
        m = self.active_model(disease.id)
        preds = self.latest_predictions(m.id, municipality_id) if m else []
        if not preds:
            raise NotFoundError("Aún no hay predicciones. Un administrador debe entrenar el modelo.")
        # By default, explain the riskiest week
        p = _peak(preds) if horizon is None else next((x for x in preds if x.horizon == horizon), preds[0])
        exp = p.explanation or {}
        factors = [ExplanationFactor(group_label=GROUP_LABELS_ES.get(f["group"], f["group"]), **f)
                   for f in exp.get("factors", [])]
        # Only the factors that move the prediction noticeably are mentioned
        threshold = max(0.1, 0.05 * p.expected_cases)
        rising = [f for f in factors if f.direction == "up" and f.contribution >= threshold]
        week, expected = label(p.year, p.epi_week), format_number_es(p.expected_cases)
        if rising:
            groups = ", ".join(f.group_label.lower() for f in rising[:3])
            summary = (f"Para la semana {week} se esperan {expected} casos. "
                       f"Lo que más empuja la predicción hacia arriba: {groups}.")
        else:
            summary = (f"Para la semana {week} se esperan {expected} casos; "
                       "ninguna señal está por encima de su valor típico.")
        return PredictionExplanation(
            municipality_id=municipality.id, municipality=municipality.name, disease_id=disease.id,
            disease=disease.name, label=week, horizon=p.horizon, level=p.risk_level,
            expected_cases=p.expected_cases, method=exp.get("method", ""), summary=summary, factors=factors,
            global_importance=m.importances if m else None)

    def history(self, disease_id: int | None = None, limit: int = 50) -> list[ModelOut]:
        codes = {d.id: d.code for d in self.db.scalars(select(Disease))}
        stmt = select(TrainedModel).order_by(TrainedModel.trained_at.desc(), TrainedModel.id.desc())
        if disease_id is not None:
            stmt = stmt.where(TrainedModel.disease_id == disease_id)
        return [model_out(m, codes.get(m.disease_id, "?")) for m in self.db.scalars(stmt.limit(limit))]
