"""Modelos de pronóstico intercambiables (patrón Strategy).

Todos predicen casos semanales en escala original. Los modelos de árboles se entrenan sobre
log(1 + casos): así un municipio de 450 000 habitantes (Pasto) y uno de 13 000 (Yacuanquer)
pesan parecido y los errores relativos se tratan igual.

- PromedioMovil: línea base. El pronóstico de las próximas semanas es el promedio de las
  últimas 4. Si un modelo de ML no le gana a esto, no vale la pena usarlo.
- BosqueAleatorio: Random Forest (promedia muchos árboles; robusto y explicable).
- GradienteBoosting: HistGradientBoosting (árboles secuenciales que corrigen el error del
  anterior; maneja valores faltantes de forma nativa, útil cuando no hay búsquedas o ventas).
"""
from abc import ABC, abstractmethod

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor


class ModeloPronostico(ABC):
    nombre: str = "modelo"
    clave: str = "modelo"

    @abstractmethod
    def ajustar(self, X: pd.DataFrame, y: pd.Series) -> "ModeloPronostico": ...

    @abstractmethod
    def predecir(self, X: pd.DataFrame) -> np.ndarray: ...

    def parametros(self) -> dict:
        return {}


class PromedioMovil(ModeloPronostico):
    nombre = "Promedio móvil (4 semanas)"
    clave = "promedio_movil"

    def ajustar(self, X, y):
        return self

    def predecir(self, X):
        return np.expm1(X["y_ma4"].to_numpy(dtype=float))


class _ModeloArboles(ModeloPronostico):
    def __init__(self, semilla: int = 42):
        self.semilla = semilla
        self.estimador = self._crear()
        self._vacias: list[str] = []

    def _crear(self):  # pragma: no cover - abstracto
        raise NotImplementedError

    def _preparar(self, X: pd.DataFrame) -> pd.DataFrame:
        # Una fuente sin ningún dato (p. ej. sin farmacias) deja la columna entera vacía; se
        # reemplaza por una constante para que el modelo simplemente la ignore.
        return X.fillna({c: 0.0 for c in self._vacias}) if self._vacias else X

    def ajustar(self, X, y):
        self._vacias = [c for c in X.columns if X[c].isna().all()]
        self.estimador.fit(self._preparar(X), np.log1p(np.asarray(y, dtype=float)))
        return self

    def predecir(self, X):
        return np.clip(np.expm1(self.predecir_log(X)), 0, None)

    def predecir_log(self, X) -> np.ndarray:
        return self.estimador.predict(self._preparar(X))

    def parametros(self) -> dict:
        p = self.estimador.get_params()
        return {k: v for k, v in p.items() if isinstance(v, (int, float, str, bool)) or v is None}


class BosqueAleatorio(_ModeloArboles):
    nombre = "Random Forest"
    clave = "random_forest"

    def _crear(self):
        # Tamaño moderado: el plan gratis de Render tiene 0,1 CPU y 512 MB
        return RandomForestRegressor(n_estimators=80, max_depth=10, min_samples_leaf=5, max_features=0.5,
                                     n_jobs=1, random_state=self.semilla)


class GradienteBoosting(_ModeloArboles):
    nombre = "Gradient Boosting"
    clave = "gradient_boosting"

    def _crear(self):
        return HistGradientBoostingRegressor(max_iter=250, learning_rate=0.05, max_leaf_nodes=15,
                                             min_samples_leaf=10, l2_regularization=1.0,
                                             random_state=self.semilla)


CANDIDATOS: list[type[_ModeloArboles]] = [BosqueAleatorio, GradienteBoosting]
