"""Índice de ventas de farmacias como fuente de datos del modelo.

No existe un dato público de ventas de medicamentos por municipio, así que la "fuente" son
los reportes semanales que hacen las farmacias registradas (tabla reportes_farmacia).
Este adaptador los convierte en una señal comparable entre municipios:

    unidades_por_farmacia = unidades de la categoría / farmacias que reportaron esa semana
    indice = unidades_por_farmacia / promedio de las 52 semanas anteriores × 100

Un índice de 140 significa "40 % más ventas que lo normal". Dividir por las farmacias que
reportaron evita que una farmacia nueva (o una que no reportó) parezca un brote.
"""
from datetime import date
from typing import Any

import pandas as pd
from sqlalchemy import select

from app.core.epi import inicio_semana
from app.fuentes.base import FuenteDatos
from app.models import Farmacia, ReporteFarmacia

VENTANA_BASE = 52


class FarmaciaFuente(FuenteDatos):
    nombre = "farmacias"

    def __init__(self, db):
        self.db = db

    def _dataframe(self, municipio_id: int | None, categorias: list[str] | None) -> pd.DataFrame:
        stmt = (select(Farmacia.municipio_id, ReporteFarmacia.farmacia_id, ReporteFarmacia.anio,
                       ReporteFarmacia.semana_epi, ReporteFarmacia.categoria, ReporteFarmacia.unidades)
                .join(Farmacia, Farmacia.id == ReporteFarmacia.farmacia_id))
        if municipio_id is not None:
            stmt = stmt.where(Farmacia.municipio_id == municipio_id)
        if categorias:
            stmt = stmt.where(ReporteFarmacia.categoria.in_(categorias))
        filas = self.db.execute(stmt).all()
        return pd.DataFrame(filas, columns=["municipio_id", "farmacia_id", "anio", "semana_epi", "categoria", "unidades"])

    @staticmethod
    def calcular_indice(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame(columns=["municipio_id", "anio", "semana_epi", "categoria", "unidades",
                                         "farmacias_reportando", "indice"])
        g = (df.groupby(["municipio_id", "categoria", "anio", "semana_epi"])
               .agg(unidades=("unidades", "sum"), farmacias_reportando=("farmacia_id", "nunique"))
               .reset_index().sort_values(["municipio_id", "categoria", "anio", "semana_epi"]))
        g["upf"] = g["unidades"] / g["farmacias_reportando"]
        # Línea base: promedio de las 52 semanas ANTERIORES (shift evita usar la semana actual)
        base = (g.groupby(["municipio_id", "categoria"])["upf"]
                  .transform(lambda s: s.shift(1).rolling(VENTANA_BASE, min_periods=4).mean()))
        g["indice"] = (g["upf"] / base * 100).round(1)
        g.loc[base.isna() | (base <= 0), "indice"] = None
        return g.drop(columns="upf")

    def obtener(self, *, municipio_id: int | None = None, categorias: list[str] | None = None,
                desde: date | None = None, **_: Any) -> list[dict[str, Any]]:
        g = self.calcular_indice(self._dataframe(municipio_id, categorias))
        filas = g.to_dict("records")
        if desde:
            filas = [f for f in filas if inicio_semana(int(f["anio"]), int(f["semana_epi"])) >= desde]
        for f in filas:
            f["indice"] = None if pd.isna(f["indice"]) else float(f["indice"])
            for k in ("municipio_id", "anio", "semana_epi", "unidades", "farmacias_reportando"):
                f[k] = int(f[k])
        return filas

    def verificar(self) -> None:
        self.db.execute(select(ReporteFarmacia.id).limit(1))
