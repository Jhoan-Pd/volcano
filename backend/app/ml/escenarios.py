"""Escenarios «¿qué pasa si…?»: modificar las señales de la última semana y volver a predecir.

El simulador no reentrena nada: toma las variables que el modelo ya ve hoy en un municipio,
cambia las de un grupo (clima, búsquedas, farmacias, volcán) y vuelve a aplicar el mismo
modelo. Sirve para entender a qué es sensible el pronóstico, no para predecir el clima.

Las variables vacías (por ejemplo, semanas sin reporte de farmacias) se llenan con el valor
típico del municipio antes de aplicar el cambio; si no, «+50 % de ventas» no tendría efecto.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

TEMPERATURA = ("temp_l0", "temp_l2", "temp_l4_6")
LLUVIA = ("lluvia_l0", "lluvia_l1", "lluvia_l2_6")
BUSQUEDAS = ("busq_l0", "busq_var")  # solo la semana actual cambia frente a su nivel habitual
FARMACIAS = ("farm_l0",)
CENIZA = "ceniza_l0_1"
CENIZA_MODERADA = 2  # escala del boletín: 0 ninguna … 3 fuerte

LIMITES = {
    "delta_temperatura_c": (-5.0, 5.0),
    "cambio_lluvia_pct": (-100.0, 200.0),
    "cambio_busquedas_pct": (-100.0, 300.0),
    "cambio_farmacias_pct": (-100.0, 300.0),
}


@dataclass(frozen=True)
class Ajustes:
    delta_temperatura_c: float = 0.0
    cambio_lluvia_pct: float = 0.0
    cambio_busquedas_pct: float = 0.0
    cambio_farmacias_pct: float = 0.0
    ceniza: bool = False

    def errores(self) -> list[str]:
        salida = []
        for campo, (minimo, maximo) in LIMITES.items():
            valor = getattr(self, campo)
            if not np.isfinite(valor) or not minimo <= valor <= maximo:
                salida.append(f"{campo} debe estar entre {minimo:g} y {maximo:g} (llegó {valor:g})")
        return salida

    @property
    def sin_cambios(self) -> bool:
        return self == Ajustes()

    def describir(self) -> str:
        partes = []
        if self.delta_temperatura_c:
            partes.append(f"{self.delta_temperatura_c:+.1f} °C".replace(".", ","))
        for campo, nombre in (("cambio_lluvia_pct", "lluvia"), ("cambio_busquedas_pct", "búsquedas"),
                              ("cambio_farmacias_pct", "ventas en farmacias")):
            if getattr(self, campo):
                partes.append(f"{getattr(self, campo):+.0f} % de {nombre}")
        if self.ceniza:
            partes.append("caída de ceniza")
        return ", ".join(partes) or "sin cambios"


def aplicar(X: pd.DataFrame, ajustes: Ajustes, tipicos: dict[str, float | None]) -> pd.DataFrame:
    """Copia de `X` (una fila) con los ajustes aplicados. No modifica la entrada."""
    X2 = X.copy()

    def base(col: str) -> pd.Series:
        tipico = tipicos.get(col)
        return X2[col].fillna(np.nan if tipico is None else tipico)

    if ajustes.delta_temperatura_c:
        for col in TEMPERATURA:
            X2[col] = base(col) + ajustes.delta_temperatura_c
    for cols, pct in ((LLUVIA, ajustes.cambio_lluvia_pct), (BUSQUEDAS, ajustes.cambio_busquedas_pct),
                      (FARMACIAS, ajustes.cambio_farmacias_pct)):
        if pct:
            for col in cols:
                X2[col] = (base(col) * (1 + pct / 100)).clip(lower=0)
    if ajustes.ceniza:
        X2[CENIZA] = np.maximum(X2[CENIZA].fillna(0), CENIZA_MODERADA)
    return X2
