"""Interchangeable forecasting estimators (Strategy pattern).

All of them predict weekly cases on the original scale. Tree models are trained on
log(1 + cases), so a municipality of 450 000 people (Pasto) and one of 13 000 (Yacuanquer)
weigh about the same and relative errors are treated alike.

- MovingAverage: the baseline. The next weeks are forecast as the mean of the last 4.
  If a machine-learning model cannot beat this, it is not worth using.
- RandomForest: averages many trees; robust and explainable.
- GradientBoosting: HistGradientBoosting, sequential trees that fix the previous one's error;
  handles missing values natively (useful when there are no searches or sales).
"""
from abc import ABC, abstractmethod

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor


class ForecastEstimator(ABC):
    name: str = "estimator"  # shown in the UI
    key: str = "estimator"   # stable identifier stored with the model

    @abstractmethod
    def fit(self, X: pd.DataFrame, y: pd.Series) -> "ForecastEstimator": ...

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> np.ndarray: ...

    def params(self) -> dict:
        return {}


class MovingAverage(ForecastEstimator):
    name = "Promedio móvil (4 semanas)"
    key = "moving_average"

    def fit(self, X, y):
        return self

    def predict(self, X):
        return np.expm1(X["y_ma4"].to_numpy(dtype=float))


class _TreeEstimator(ForecastEstimator):
    def __init__(self, seed: int = 42):
        self.seed = seed
        self.estimator = self._build()
        self._empty_columns: list[str] = []

    def _build(self):  # pragma: no cover - abstract
        raise NotImplementedError

    def prepare(self, X: pd.DataFrame) -> pd.DataFrame:
        # A source with no data at all (e.g. no pharmacies) leaves a whole column empty; it is
        # replaced with a constant so the model simply ignores it.
        return X.fillna({c: 0.0 for c in self._empty_columns}) if self._empty_columns else X

    def fit(self, X, y):
        self._empty_columns = [c for c in X.columns if X[c].isna().all()]
        self.estimator.fit(self.prepare(X), np.log1p(np.asarray(y, dtype=float)))
        return self

    def predict(self, X):
        return np.clip(np.expm1(self.predict_log(X)), 0, None)

    def predict_log(self, X) -> np.ndarray:
        return self.estimator.predict(self.prepare(X))

    def params(self) -> dict:
        p = self.estimator.get_params()
        return {k: v for k, v in p.items() if isinstance(v, (int, float, str, bool)) or v is None}


class RandomForest(_TreeEstimator):
    name = "Random Forest"
    key = "random_forest"

    def _build(self):
        # Moderate size: Render's free plan has 0.1 CPU and 512 MB
        return RandomForestRegressor(n_estimators=80, max_depth=10, min_samples_leaf=5, max_features=0.5,
                                     n_jobs=1, random_state=self.seed)


class GradientBoosting(_TreeEstimator):
    name = "Gradient Boosting"
    key = "gradient_boosting"

    def _build(self):
        return HistGradientBoostingRegressor(max_iter=250, learning_rate=0.05, max_leaf_nodes=15,
                                             min_samples_leaf=10, l2_regularization=1.0,
                                             random_state=self.seed)


CANDIDATES: list[type[_TreeEstimator]] = [RandomForest, GradientBoosting]
