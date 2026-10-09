"""Explicabilidad local: "¿por qué subió el riesgo?".

Método de oclusión por grupos: para una predicción concreta se reemplazan las variables de
un grupo (p. ej. "Búsquedas en internet") por su valor típico (la mediana histórica) y se
vuelve a predecir. La diferencia es la contribución del grupo, en casos:

    contribución(grupo) = predicción real − predicción con el grupo en su valor típico

Es más fácil de explicar que SHAP y no necesita librerías extra. Además, se generan frases
legibles a partir de los valores observados (búsquedas +40 %, ceniza reciente, etc.).
"""
import math

import numpy as np
import pandas as pd

from app.ml.dataset import GRUPOS


def contribuciones(modelo, x: pd.DataFrame, medianas: dict) -> tuple[float, dict[str, float]]:
    base = float(modelo.predecir(x)[0])
    salida = {}
    for grupo, variables in GRUPOS.items():
        x2 = x.copy()
        for v in variables:
            x2[v] = np.nan if medianas.get(v) is None else medianas[v]
        salida[grupo] = round(base - float(modelo.predecir(x2)[0]), 2)
    return base, salida


def _pct(v: float | None) -> str:
    return f"{'+' if v >= 0 else '−'}{abs(v):.0f} %"


def _ok(v) -> bool:
    return v is not None and not (isinstance(v, float) and math.isnan(v))


def señales(fila: pd.Series, medianas: dict, terminos: list[str], categorias: list[str]) -> dict[str, str]:
    """Frases que describen qué está pasando con cada grupo de variables en la semana actual."""
    m: dict[str, str] = {}
    if _ok(fila.get("y_l0")) and _ok(fila.get("y_ma8")):
        actual, media = math.expm1(fila["y_l0"]), math.expm1(fila["y_ma8"])
        if media > 0.5:
            cambio = (actual / media - 1) * 100
            m["Casos recientes"] = (f"Los casos de la última semana ({actual:.0f}) están {_pct(cambio)} frente al "
                                    f"promedio de las 8 semanas anteriores ({media:.1f}).")
    if _ok(fila.get("busq_var")):
        cambio = (fila["busq_var"] - 1) * 100
        m["Búsquedas en internet"] = (f"Las búsquedas en internet de «{', '.join(terminos)}» en Nariño están "
                                      f"{_pct(cambio)} respecto a su nivel habitual.")
    if _ok(fila.get("farm_l0")):
        cambio = fila["farm_l0"] - 100
        nombres = ", ".join(c.replace("_", " ").lower() for c in categorias) or "productos asociados"
        m["Ventas en farmacias"] = f"Las ventas de {nombres} en las farmacias del municipio están {_pct(cambio)} de lo normal."
    partes = []
    if _ok(fila.get("lluvia_l2_6")) and _ok(medianas.get("lluvia_l2_6")) and medianas["lluvia_l2_6"] > 0:
        partes.append(f"lluvia de las semanas previas {_pct((fila['lluvia_l2_6'] / medianas['lluvia_l2_6'] - 1) * 100)}")
    if _ok(fila.get("temp_l0")) and _ok(medianas.get("temp_l0")):
        partes.append(f"temperatura {fila['temp_l0'] - medianas['temp_l0']:+.1f} °C")
    if partes:
        m["Clima"] = "Frente a lo típico: " + ", ".join(partes) + "."
    if _ok(fila.get("ceniza_l0_1")) and fila["ceniza_l0_1"] > 0:
        m["Actividad volcánica"] = ("Hubo caída de ceniza reciente en el municipio "
                                    f"(intensidad {int(fila['ceniza_l0_1'])} de 3).")
    elif _ok(fila.get("so2_l0")) and _ok(medianas.get("so2_l0")) and medianas["so2_l0"]:
        cambio = (fila["so2_l0"] / medianas["so2_l0"] - 1) * 100
        if abs(cambio) >= 25:
            m["Actividad volcánica"] = f"La emisión de SO₂ del Galeras está {_pct(cambio)} frente a su mediana."
    if _ok(fila.get("y_anio_ant")):
        m["Estacionalidad"] = (f"En estas mismas semanas del año pasado hubo en promedio "
                               f"{math.expm1(fila['y_anio_ant']):.1f} casos por semana.")
    return m


def explicar(modelo, x: pd.DataFrame, fila: pd.Series, medianas: dict, terminos: list[str],
             categorias: list[str]) -> dict:
    base, contrib = contribuciones(modelo, x, medianas)
    frases = señales(fila, medianas, terminos, categorias)
    factores = [
        {"grupo": g, "contribucion": c, "direccion": "sube" if c > 0 else "baja" if c < 0 else "neutral",
         "mensaje": frases.get(g)}
        for g, c in sorted(contrib.items(), key=lambda kv: -abs(kv[1]))
    ]
    return {"metodo": "oclusión por grupos (valor típico = mediana histórica)", "prediccion": round(base, 2),
            "factores": factores}
