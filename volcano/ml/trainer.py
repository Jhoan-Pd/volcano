"""Training, temporal validation and model selection.

Procedure (per disease, all municipalities together):
1. Temporal validation: the last `test_weeks` weeks (52 by default) are the test set and
   everything before is the training set. The future is never mixed with the past (no random
   cross-validation).
2. Direct strategy: one model per horizon (t+1, t+2, t+3, t+4).
3. The baseline (moving average) and the candidates are compared with MAE and RMSE.
4. The candidate with the lowest mean MAE wins and is retrained with ALL the data.
5. 80 % interval: percentiles 10 and 90 of the test residuals (log scale).
6. Permutation importance on the test set (how much the MAE worsens when a feature is
   shuffled), aggregated by group.
"""
import io
from dataclasses import dataclass, field

import joblib
import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance

from volcano.ml.dataset import trainable_rows
from volcano.ml.estimators import CANDIDATES, MovingAverage
from volcano.ml.features import FEATURE_GROUPS, FEATURES, HORIZONS, group_of
from volcano.ml.progress import Progress, ProgressEvent, Stage, no_progress
from volcano.shared.epi import shift

# Bumped whenever the artifact layout or the feature names change. Artifacts with another
# version are not loaded: the engine retrains instead (see volcano.engine.startup).
ARTIFACT_VERSION = "2"


def mae(y, p) -> float:
    return float(np.mean(np.abs(np.asarray(y) - np.asarray(p))))


def rmse(y, p) -> float:
    return float(np.sqrt(np.mean((np.asarray(y) - np.asarray(p)) ** 2)))


@dataclass
class TrainingResult:
    algorithm: str
    key: str
    baseline_mae: float
    baseline_rmse: float
    model_mae: float
    model_rmse: float
    sample_count: int
    metrics: dict
    importances: dict
    quantiles: dict
    backtest: list
    artifact: bytes
    params: dict = field(default_factory=dict)


class InsufficientDataError(ValueError):
    pass


class IncompatibleArtifactError(ValueError):
    """The stored artifact was written by another version of the code; retrain the model."""


class Trainer:
    def __init__(self, test_weeks: int = 52, seed: int = 42, permutation_repeats: int = 4):
        self.test_weeks = test_weeks
        self.seed = seed
        self.repeats = permutation_repeats

    def _split(self, df: pd.DataFrame, h: int) -> tuple[pd.DataFrame, pd.DataFrame]:
        data = trainable_rows(df, h)
        cutoff = data["t_idx"].max() - self.test_weeks
        return data[data["t_idx"] <= cutoff], data[data["t_idx"] > cutoff]

    def train(self, df: pd.DataFrame, progress: Progress = no_progress) -> TrainingResult:
        if df.empty or trainable_rows(df, 1)["t_idx"].nunique() < self.test_weeks + 52:
            raise InsufficientDataError("Se necesitan al menos 2 años de semanas con casos para entrenar")

        metrics: dict[str, dict[str, dict[str, float]]] = {MovingAverage.key: {}}
        predictions: dict[str, dict[int, np.ndarray]] = {}
        tests: dict[int, pd.DataFrame] = {}
        fitted: dict[str, dict[int, object]] = {}
        steps = len(HORIZONS) * (len(CANDIDATES) + 1)  # compare candidates + retrain the winner
        step = 0
        for h in HORIZONS:
            train, test = self._split(df, h)
            tests[h] = test
            y_test = test[f"y_h{h}"].to_numpy()
            base = MovingAverage().predict(test)
            metrics[MovingAverage.key][str(h)] = {"mae": mae(y_test, base), "rmse": rmse(y_test, base)}
            for cls in CANDIDATES:
                m = cls(self.seed).fit(train[FEATURES], train[f"y_h{h}"])
                p = m.predict(test[FEATURES])
                metrics.setdefault(cls.key, {})[str(h)] = {"mae": mae(y_test, p), "rmse": rmse(y_test, p)}
                predictions.setdefault(cls.key, {})[h] = p
                fitted.setdefault(cls.key, {})[h] = m
                step += 1
                error = metrics[cls.key][str(h)]["mae"]
                progress(ProgressEvent(Stage.CANDIDATE, f"t+{h} · {cls.name}: MAE {error:.2f}", step / steps,
                                       algorithm=cls.name, mae=error,
                                       baseline_mae=metrics[MovingAverage.key][str(h)]["mae"]))

        def mean_metric(key: str, metric: str) -> float:
            return float(np.mean([v[metric] for v in metrics[key].values()]))

        best = min(CANDIDATES, key=lambda c: mean_metric(c.key, "mae"))
        summary = {k: {"mae": round(mean_metric(k, "mae"), 3), "rmse": round(mean_metric(k, "rmse"), 3)}
                   for k in metrics}

        # 80 % interval from the log-scale residuals
        quantiles = {}
        for h in HORIZONS:
            y_log = np.log1p(tests[h][f"y_h{h}"].to_numpy())
            p_log = fitted[best.key][h].predict_log(tests[h][FEATURES])
            r = y_log - p_log
            quantiles[str(h)] = [float(np.quantile(r, 0.10)), float(np.quantile(r, 0.90))]

        importances = self._importances(fitted[best.key][1], tests[1])

        # One-week-ahead predictions over the test period: draws "predicted vs. observed"
        backtest = []
        for row, p in zip(tests[1].itertuples(), predictions[best.key][1], strict=True):
            y, w = shift(int(row.year), int(row.epi_week), 1)
            backtest.append({"municipality_id": int(row.municipality_id), "year": y, "epi_week": w,
                             "observed": float(row.y_h1), "predicted": round(float(p), 2)})

        # Retrain the winner with all the data (more information for the future)
        final = {}
        for h in HORIZONS:
            everything = trainable_rows(df, h)
            final[h] = best(self.seed).fit(everything[FEATURES], everything[f"y_h{h}"])
            step += 1
            progress(ProgressEvent(Stage.CANDIDATE, f"t+{h} · {best.name} reentrenado con todos los datos",
                                   step / steps, algorithm=best.name))
        medians = {f: (None if pd.isna(v) else float(v)) for f, v in df[FEATURES].median().items()}
        artifact = self.serialize({"version": ARTIFACT_VERSION, "key": best.key, "features": FEATURES,
                                   "models": final, "medians": medians, "quantiles": quantiles})

        return TrainingResult(
            algorithm=best.name, key=best.key,
            baseline_mae=summary[MovingAverage.key]["mae"], baseline_rmse=summary[MovingAverage.key]["rmse"],
            model_mae=summary[best.key]["mae"], model_rmse=summary[best.key]["rmse"],
            sample_count=len(trainable_rows(df, 1)),
            metrics={"summary": summary, "by_horizon": metrics, "test_weeks": self.test_weeks},
            importances=importances, quantiles=quantiles, backtest=backtest, artifact=artifact,
            params=final[1].params(),
        )

    def _importances(self, model, test: pd.DataFrame) -> dict:
        r = permutation_importance(
            model.estimator, model.prepare(test[FEATURES]), np.log1p(test["y_h1"].to_numpy()),
            scoring="neg_mean_absolute_error",
            n_repeats=self.repeats, random_state=self.seed, n_jobs=1)
        values = {f: max(float(v), 0.0) for f, v in zip(FEATURES, r.importances_mean, strict=True)}
        total = sum(values.values()) or 1.0
        by_feature = {f: round(100 * v / total, 2) for f, v in sorted(values.items(), key=lambda x: -x[1])}
        by_group = {g: round(sum(by_feature[f] for f in fs), 2) for g, fs in FEATURE_GROUPS.items()}
        return {
            "method": "permutation (MAE increase on the test set, t+1)",
            "groups": dict(sorted(by_group.items(), key=lambda x: -x[1])),
            "features": {f: {"importance": v, "group": group_of(f)} for f, v in list(by_feature.items())[:12]},
        }

    @staticmethod
    def serialize(obj: dict) -> bytes:
        buf = io.BytesIO()
        joblib.dump(obj, buf, compress=3)
        return buf.getvalue()

    @staticmethod
    def deserialize(data: bytes) -> dict:
        """Load an artifact, refusing the ones written by another version of the code."""
        try:
            artifact = joblib.load(io.BytesIO(data))
        except (AttributeError, ModuleNotFoundError, ImportError) as exc:  # classes moved or renamed
            raise IncompatibleArtifactError(f"Artifact cannot be loaded: {exc}") from exc
        if not isinstance(artifact, dict) or artifact.get("version") != ARTIFACT_VERSION:
            found = artifact.get("version") if isinstance(artifact, dict) else type(artifact).__name__
            raise IncompatibleArtifactError(f"Artifact version {found!r}, expected {ARTIFACT_VERSION!r}")
        return artifact
