"""Canal endémico y semáforo de riesgo.

Método: para la semana S del año A se toman los casos de las semanas S-1, S y S+1 de los
5 años anteriores (hasta 15 valores) y se calculan percentiles. Con los umbrales por
defecto de cada enfermedad:
    VERDE    casos <= P50           (zona de seguridad/éxito)
    AMARILLO P50 < casos <= P75     (zona de alerta)
    NARANJA  P75 < casos <= P90     (zona de epidemia)
    ROJO     casos > P90            (brote: muy por encima de lo esperado)
Los percentiles son configurables por enfermedad desde el panel admin.

Piso mínimo: con conteos muy bajos (p. ej. dengue en Pasto, P90 = 0) un solo caso
dispararía ROJO. Por eso el nivel solo sube de VERDE si hay al menos MIN_CASOS_ALERTA casos.
"""
from dataclasses import dataclass

import numpy as np

from app.core.epi import desplazar, semanas_del_anio
from app.models.enums import NivelRiesgo

ANIOS_HISTORICOS = 5
VENTANA_SEMANAS = 1
MIN_CASOS_ALERTA = 3

ORDEN_NIVELES = [NivelRiesgo.VERDE, NivelRiesgo.AMARILLO, NivelRiesgo.NARANJA, NivelRiesgo.ROJO]


@dataclass(frozen=True)
class UmbralesCanal:
    amarillo: float
    naranja: float
    rojo: float


def semanas_referencia(anio: int, semana: int, anios: int = ANIOS_HISTORICOS,
                       ventana: int = VENTANA_SEMANAS) -> list[tuple[int, int]]:
    """Pares (año, semana) históricos comparables con la semana objetivo."""
    pares = []
    for a in range(anio - anios, anio):
        s = min(semana, semanas_del_anio(a))  # años sin semana 53 usan la 52
        for d in range(-ventana, ventana + 1):
            pares.append(desplazar(a, s, d))
    return pares


def calcular_umbrales(valores: list[float], p_amarillo: int, p_naranja: int, p_rojo: int) -> UmbralesCanal | None:
    if len(valores) < 3:
        return None
    arr = np.asarray(valores, dtype=float)
    a, n, r = np.percentile(arr, [p_amarillo, p_naranja, p_rojo])
    return UmbralesCanal(round(float(a), 2), round(float(n), 2), round(float(r), 2))


def clasificar(casos: float, u: UmbralesCanal | None) -> NivelRiesgo:
    if u is None or casos < MIN_CASOS_ALERTA:
        return NivelRiesgo.VERDE
    if casos > u.rojo:
        return NivelRiesgo.ROJO
    if casos > u.naranja:
        return NivelRiesgo.NARANJA
    if casos > u.amarillo:
        return NivelRiesgo.AMARILLO
    return NivelRiesgo.VERDE


def nivel_maximo(niveles: list[str]) -> str:
    if not niveles:
        return NivelRiesgo.VERDE.value
    return max(niveles, key=lambda n: ORDEN_NIVELES.index(NivelRiesgo(n)))
