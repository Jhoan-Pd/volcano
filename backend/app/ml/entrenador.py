"""Entrenamiento, validación temporal y selección del modelo.

Procedimiento (para cada enfermedad, con todos los municipios juntos):
1. Validación temporal: las últimas `semanas_prueba` semanas (por defecto 52) son el
   conjunto de prueba y todo lo anterior el de entrenamiento. Nunca se mezcla el futuro
   con el pasado (no se usa validación cruzada aleatoria).
2. Estrategia directa: un modelo por horizonte (t+1, t+2, t+3, t+4).
3. Se comparan la línea base (promedio móvil) y los candidatos con MAE y RMSE.
4. Se elige el candidato con menor MAE promedio y se reentrena con TODOS los datos.
5. Intervalo del 80 %: percentiles 10 y 90 de los residuos (en escala logarítmica) en prueba.
6. Importancia de variables por permutación en prueba (cuánto empeora el MAE si se
   desordena una variable), agregada por grupo.
"""
import io
from dataclasses import dataclass, field

import joblib
import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance

from app.core.epi import desplazar
from app.ml.dataset import FEATURES, GRUPOS, HORIZONTES, filas_entrenables, grupo_de
from app.ml.modelos import CANDIDATOS, PromedioMovil

VERSION_ARTEFACTO = "1"


def mae(y, p) -> float:
    return float(np.mean(np.abs(np.asarray(y) - np.asarray(p))))


def rmse(y, p) -> float:
    return float(np.sqrt(np.mean((np.asarray(y) - np.asarray(p)) ** 2)))


@dataclass
class ResultadoEntrenamiento:
    algoritmo: str
    clave: str
    mae_base: float
    rmse_base: float
    mae_modelo: float
    rmse_modelo: float
    n_muestras: int
    metricas: dict
    importancias: dict
    cuantiles: dict
    backtest: list
    artefacto: bytes
    parametros: dict = field(default_factory=dict)


class DatosInsuficientesError(ValueError):
    pass


class Entrenador:
    def __init__(self, semanas_prueba: int = 52, semilla: int = 42, repeticiones_permutacion: int = 4):
        self.semanas_prueba = semanas_prueba
        self.semilla = semilla
        self.repeticiones = repeticiones_permutacion

    def _particion(self, df: pd.DataFrame, h: int) -> tuple[pd.DataFrame, pd.DataFrame]:
        datos = filas_entrenables(df, h)
        corte = datos["t_idx"].max() - self.semanas_prueba
        return datos[datos["t_idx"] <= corte], datos[datos["t_idx"] > corte]

    def entrenar(self, df: pd.DataFrame) -> ResultadoEntrenamiento:
        if df.empty or filas_entrenables(df, 1)["t_idx"].nunique() < self.semanas_prueba + 52:
            raise DatosInsuficientesError("Se necesitan al menos 2 años de semanas con casos para entrenar")

        metricas: dict[str, dict[str, dict[str, float]]] = {"promedio_movil": {}}
        predicciones: dict[str, dict[int, np.ndarray]] = {}
        pruebas: dict[int, pd.DataFrame] = {}
        modelos_h: dict[str, dict[int, object]] = {}
        for h in HORIZONTES:
            train, test = self._particion(df, h)
            pruebas[h] = test
            y_test = test[f"y_h{h}"].to_numpy()
            base = PromedioMovil().predecir(test)
            metricas["promedio_movil"][str(h)] = {"mae": mae(y_test, base), "rmse": rmse(y_test, base)}
            for cls in CANDIDATOS:
                m = cls(self.semilla).ajustar(train[FEATURES], train[f"y_h{h}"])
                p = m.predecir(test[FEATURES])
                metricas.setdefault(cls.clave, {})[str(h)] = {"mae": mae(y_test, p), "rmse": rmse(y_test, p)}
                predicciones.setdefault(cls.clave, {})[h] = p
                modelos_h.setdefault(cls.clave, {})[h] = m

        def promedio(clave: str, metrica: str) -> float:
            return float(np.mean([v[metrica] for v in metricas[clave].values()]))

        mejor = min((c for c in CANDIDATOS), key=lambda c: promedio(c.clave, "mae"))
        resumen = {c: {"mae": round(promedio(c, "mae"), 3), "rmse": round(promedio(c, "rmse"), 3)} for c in metricas}

        # Intervalo del 80 % a partir de los residuos en escala log
        cuantiles = {}
        for h in HORIZONTES:
            y_log = np.log1p(pruebas[h][f"y_h{h}"].to_numpy())
            p_log = modelos_h[mejor.clave][h].predecir_log(pruebas[h][FEATURES])
            r = y_log - p_log
            cuantiles[str(h)] = [float(np.quantile(r, 0.10)), float(np.quantile(r, 0.90))]

        importancias = self._importancias(modelos_h[mejor.clave][1], pruebas[1])

        # Predicción a 1 semana en el periodo de prueba: permite dibujar "predicho vs. observado"
        backtest = []
        for fila, p in zip(pruebas[1].itertuples(), predicciones[mejor.clave][1]):
            a, s = desplazar(int(fila.anio), int(fila.semana_epi), 1)
            backtest.append({"municipio_id": int(fila.municipio_id), "anio": a, "semana_epi": s,
                             "real": float(fila.y_h1), "predicho": round(float(p), 2)})

        # Reentrenar el modelo elegido con todos los datos (más información para el futuro)
        finales = {}
        for h in HORIZONTES:
            todos = filas_entrenables(df, h)
            finales[h] = mejor(self.semilla).ajustar(todos[FEATURES], todos[f"y_h{h}"])
        medianas = {f: (None if pd.isna(v) else float(v)) for f, v in df[FEATURES].median().items()}
        artefacto = self.serializar({"version": VERSION_ARTEFACTO, "clave": mejor.clave, "features": FEATURES,
                                     "modelos": finales, "medianas": medianas, "cuantiles": cuantiles})

        return ResultadoEntrenamiento(
            algoritmo=mejor.nombre, clave=mejor.clave,
            mae_base=resumen["promedio_movil"]["mae"], rmse_base=resumen["promedio_movil"]["rmse"],
            mae_modelo=resumen[mejor.clave]["mae"], rmse_modelo=resumen[mejor.clave]["rmse"],
            n_muestras=int(len(filas_entrenables(df, 1))),
            metricas={"resumen": resumen, "por_horizonte": metricas, "semanas_prueba": self.semanas_prueba},
            importancias=importancias, cuantiles=cuantiles, backtest=backtest, artefacto=artefacto,
            parametros=finales[1].parametros(),
        )

    def _importancias(self, modelo, test: pd.DataFrame) -> dict:
        r = permutation_importance(
            modelo.estimador, modelo._preparar(test[FEATURES]), np.log1p(test["y_h1"].to_numpy()), scoring="neg_mean_absolute_error",
            n_repeats=self.repeticiones, random_state=self.semilla, n_jobs=1)
        valores = {f: max(float(v), 0.0) for f, v in zip(FEATURES, r.importances_mean)}
        total = sum(valores.values()) or 1.0
        por_variable = {f: round(100 * v / total, 2) for f, v in sorted(valores.items(), key=lambda x: -x[1])}
        por_grupo = {g: round(sum(por_variable[f] for f in fs), 2) for g, fs in GRUPOS.items()}
        return {
            "metodo": "permutación (aumento del MAE en prueba, t+1)",
            "grupos": dict(sorted(por_grupo.items(), key=lambda x: -x[1])),
            "variables": {f: {"importancia": v, "grupo": grupo_de(f)} for f, v in list(por_variable.items())[:12]},
        }

    @staticmethod
    def serializar(obj: dict) -> bytes:
        buf = io.BytesIO()
        joblib.dump(obj, buf, compress=3)
        return buf.getvalue()

    @staticmethod
    def deserializar(datos: bytes) -> dict:
        return joblib.load(io.BytesIO(datos))
