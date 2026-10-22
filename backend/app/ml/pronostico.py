"""Aplicar un modelo entrenado a la última semana conocida de cada municipio.

Antes este cálculo vivía dentro de `PrediccionService.predecir_enfermedad`, mezclado con la
escritura en la base de datos. Separarlo permite usar exactamente la misma lógica en dos lugares:

- el servicio de predicción, que guarda las predicciones semanales en la BD;
- el motor gRPC, que mantiene el modelo en memoria y responde pronósticos y escenarios
  «¿qué pasa si…?» sin tocar la BD.

`Pronosticador` no hace consultas: recibe el dataset ya construido y el artefacto ya
deserializado, y solo hace cálculos (función pura de sus entradas).
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.core.epi import desplazar
from app.ml.dataset import FEATURES, HORIZONTES, ultima_fila_por_municipio
from app.models.enums import NivelRiesgo
from app.services import riesgo_service as rs


@dataclass(frozen=True)
class PuntoPronostico:
    anio: int
    semana_epi: int
    horizonte: int
    casos_esperados: float
    limite_inferior: float
    limite_superior: float
    nivel: NivelRiesgo
    umbrales: rs.UmbralesCanal | None


class Pronosticador:
    """Pronósticos a 1-4 semanas de una enfermedad, para cada municipio del dataset."""

    def __init__(self, enfermedad, artefacto: dict, df: pd.DataFrame):
        self.enfermedad = enfermedad
        self.artefacto = artefacto
        self._ultimas: dict[int, pd.Series] = {}
        self._series: dict[int, dict[tuple[int, int], float]] = {}
        self._tipicos: dict[int, dict[str, float | None]] = {}
        if df.empty:
            return
        self._ultimas = {int(f["municipio_id"]): f for _, f in ultima_fila_por_municipio(df).iterrows()}
        medianas = artefacto["medianas"]
        for clave, grupo in df.groupby("municipio_id"):
            mid = int(clave)
            self._series[mid] = {(int(a), int(s)): c for a, s, c in
                                 grupo[["anio", "semana_epi", "casos"]].itertuples(index=False)}
            # "Valor típico" del propio municipio (Pasto a 2 527 m no se compara con Consacá a 1 730 m)
            self._tipicos[mid] = {f: (medianas.get(f) if pd.isna(v) else float(v))
                                  for f, v in grupo[FEATURES].median().items()}

    # ── entradas ──────────────────────────────────────────────────────────────
    def municipios(self) -> list[int]:
        return sorted(self._ultimas)

    def tiene(self, municipio_id: int) -> bool:
        return municipio_id in self._ultimas

    def fila(self, municipio_id: int) -> pd.Series:
        """Variables de la última semana con datos (lo que se sabe hoy)."""
        return self._ultimas[municipio_id]

    def entrada(self, municipio_id: int) -> pd.DataFrame:
        fila = self._ultimas[municipio_id]
        return pd.DataFrame([fila[FEATURES].astype(float)], columns=FEATURES)

    def tipicos(self, municipio_id: int) -> dict[str, float | None]:
        return self._tipicos[municipio_id]

    def semana_base(self, municipio_id: int) -> tuple[int, int]:
        fila = self._ultimas[municipio_id]
        return int(fila["anio"]), int(fila["semana_epi"])

    def estimador(self, horizonte: int):
        return self.artefacto["modelos"][horizonte]

    # ── cálculo ───────────────────────────────────────────────────────────────
    def umbrales(self, municipio_id: int, anio: int, semana: int) -> rs.UmbralesCanal | None:
        serie = self._series.get(municipio_id, {})
        enf = self.enfermedad
        return rs.calcular_umbrales([serie[p] for p in rs.semanas_referencia(anio, semana) if p in serie],
                                    enf.umbral_amarillo_pct, enf.umbral_naranja_pct, enf.umbral_rojo_pct)

    def pronosticar(self, municipio_id: int, X: pd.DataFrame | None = None) -> list[PuntoPronostico]:
        """Pronóstico de las próximas semanas. `X` permite pasar variables modificadas
        (un escenario); si se omite se usan las de la última semana observada."""
        if X is None:
            X = self.entrada(municipio_id)
        anio, semana = self.semana_base(municipio_id)
        puntos = []
        for h in HORIZONTES:
            p_log = float(self.estimador(h).predecir_log(X)[0])
            q10, q90 = self.artefacto["cuantiles"][str(h)]
            esperado = max(float(np.expm1(p_log)), 0.0)
            a, s = desplazar(anio, semana, h)
            u = self.umbrales(municipio_id, a, s)
            puntos.append(PuntoPronostico(
                anio=a, semana_epi=s, horizonte=h, casos_esperados=round(esperado, 2),
                limite_inferior=round(max(float(np.expm1(p_log + q10)), 0.0), 2),
                limite_superior=round(max(float(np.expm1(p_log + q90)), 0.0), 2),
                nivel=rs.clasificar(esperado, u), umbrales=u))
        return puntos
