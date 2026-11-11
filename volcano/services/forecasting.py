"""Write side of the predictions: trains models and stores the next 4 weeks of predictions.

Every training run adds a row to `trained_models` (date, algorithm, baseline and model MAE/RMSE,
importances). Only the latest model of each disease stays active and keeps its serialized artifact;
older ones keep their metrics for the history but lose the binary (the free database has 0.5 GB).

Only the engine imports this module: it pulls in scikit-learn and the dataset builder.
"""
import logging
from datetime import UTC, datetime

import pandas as pd
from sqlalchemy import delete, update

from volcano.ml.dataset import DatasetBuilder
from volcano.ml.explainer import explain
from volcano.ml.forecaster import Forecaster
from volcano.ml.progress import Progress, ProgressEvent, Stage, no_progress, scaled
from volcano.ml.trainer import IncompatibleArtifactError, InsufficientDataError, Trainer
from volcano.models import Disease, Prediction, TrainedModel
from volcano.repositories.domain import DiseaseRepository
from volcano.services.predictions import PredictionQueryService
from volcano.shared.errors import NotFoundError

logger = logging.getLogger("volcano.forecasting")


class ForecastingService:
    def __init__(self, db, trainer: Trainer | None = None):
        self.db = db
        self.trainer = trainer or Trainer()
        self.diseases = DiseaseRepository(db)
        self.queries = PredictionQueryService(db)

    # ── training ─────────────────────────────────────────────────────────────
    def train(self, disease_id: int | None = None,
              progress: Progress = no_progress) -> tuple[list[TrainedModel], list[str]]:
        diseases = self.diseases.active()
        if disease_id is not None:
            diseases = [d for d in diseases if d.id == disease_id]
            if not diseases:
                raise NotFoundError(f"Enfermedad {disease_id} no existe o está inactiva")
        models, errors = [], []
        n = len(diseases)
        for i, disease in enumerate(diseases):
            stretch = scaled(progress, i / n, (i + 1) / n, disease=disease.name)
            try:
                models.append(self.train_disease(disease, stretch))
            except InsufficientDataError as exc:
                errors.append(f"{disease.code}: {exc}")
                stretch(ProgressEvent(Stage.WARNING, f"{disease.name}: {exc}", 1.0))
        return models, errors

    def train_disease(self, disease: Disease, progress: Progress = no_progress) -> TrainedModel:
        progress(ProgressEvent(Stage.DATASET, f"{disease.name}: construyendo el dataset semanal", 0.0))
        df = DatasetBuilder(self.db).build(disease)
        r = self.trainer.train(df, scaled(progress, 0.05, 0.9))
        now = datetime.now(UTC)
        # Only the current model keeps its binary
        self.db.execute(update(TrainedModel).where(TrainedModel.disease_id == disease.id)
                        .values(active=False, artifact=None))
        m = TrainedModel(
            disease_id=disease.id, algorithm=r.algorithm, version=now.strftime("%Y%m%d-%H%M%S"),
            trained_at=now, baseline_mae=r.baseline_mae, baseline_rmse=r.baseline_rmse, model_mae=r.model_mae,
            model_rmse=r.model_rmse, sample_count=r.sample_count, importances=r.importances,
            parameters={"key": r.key, "metrics": r.metrics, "quantiles": r.quantiles, "backtest": r.backtest,
                        "hyperparameters": r.params},
            artifact=r.artifact, active=True,
        )
        self.db.add(m)
        self.db.commit()
        self.queries.clear_cache()
        logger.info("Model %s: %s MAE %.3f (baseline %.3f)", disease.code, r.algorithm, r.model_mae, r.baseline_mae)
        progress(ProgressEvent(Stage.MODEL_READY, f"{disease.name}: gana {r.algorithm} (MAE {r.model_mae:.2f} "
                               f"frente a {r.baseline_mae:.2f} del promedio móvil)", 0.9, algorithm=r.algorithm,
                               mae=r.model_mae, baseline_mae=r.baseline_mae))
        created = self.predict_disease(disease, m, df)
        progress(ProgressEvent(Stage.PREDICTIONS, f"{disease.name}: {created} predicciones guardadas", 1.0))
        return m

    # ── prediction ───────────────────────────────────────────────────────────
    def diseases_needing_training(self) -> list[Disease]:
        """Active diseases whose active model is missing or was written by another code version."""
        pending = []
        for disease in self.diseases.active():
            m = self.queries.active_model(disease.id)
            if m is None or m.artifact is None:
                pending.append(disease)
                continue
            try:
                Trainer.deserialize(m.artifact)
            except IncompatibleArtifactError as exc:
                logger.warning("Model %s must be retrained: %s", disease.code, exc)
                pending.append(disease)
        return pending

    def predict_all(self) -> int:
        total = 0
        for disease in self.diseases.active():
            m = self.queries.active_model(disease.id)
            if m is None or not m.artifact:
                continue
            try:
                total += self.predict_disease(disease, m)
            except IncompatibleArtifactError as exc:
                logger.warning("Skipping %s: %s", disease.code, exc)
        return total

    def predict_disease(self, disease: Disease, model: TrainedModel, df: pd.DataFrame | None = None) -> int:
        if df is None:
            df = DatasetBuilder(self.db).build(disease)
        if df.empty:
            return 0
        forecaster = Forecaster(disease, Trainer.deserialize(model.artifact), df)
        terms, categories = disease.search_term_list, disease.pharmacy_category_list
        created = 0
        for mid in forecaster.municipalities():
            X, row, typical = forecaster.inputs(mid), forecaster.row(mid), forecaster.typical(mid)
            for point in forecaster.forecast(mid, X):
                self.db.execute(delete(Prediction).where(
                    Prediction.model_id == model.id, Prediction.municipality_id == mid,
                    Prediction.year == point.year, Prediction.epi_week == point.epi_week,
                    Prediction.horizon == point.horizon))
                explanation = explain(forecaster.estimator(point.horizon), X, row, typical, terms, categories)
                explanation["thresholds"] = point.thresholds.as_dict() if point.thresholds else None
                self.db.add(Prediction(
                    model_id=model.id, municipality_id=mid, disease_id=disease.id, year=point.year,
                    epi_week=point.epi_week, horizon=point.horizon, expected_cases=point.expected_cases,
                    lower_bound=point.lower_bound, upper_bound=point.upper_bound,
                    risk_level=point.level.value, explanation=explanation,
                ))
                created += 1
        self.db.commit()
        self.queries.clear_cache()
        return created
