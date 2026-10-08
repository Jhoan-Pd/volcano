"""Exporta las búsquedas guardadas en BD al CSV de respaldo de Google Trends.

Uso (desde backend/):  python -m app.seed.exportar_trends [--salida data/trends/trends_respaldo_narino.csv]

Sirve para regenerar el respaldo que usa `CsvTrendsFuente` cuando pytrends falla.
"""
import argparse
import csv
from pathlib import Path

from sqlalchemy import select

from app.db.session import SessionLocal
from app.fuentes.trends import RAIZ_BACKEND
from app.models import TendenciaBusqueda

SALIDA = RAIZ_BACKEND / "data" / "trends" / "trends_respaldo_narino.csv"


def exportar(salida: Path = SALIDA) -> int:
    salida.parent.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db, open(salida, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["termino", "fecha_semana", "indice", "region", "es_simulado"])
        n = 0
        for t in db.scalars(select(TendenciaBusqueda).order_by(TendenciaBusqueda.termino, TendenciaBusqueda.fecha_semana)):
            w.writerow([t.termino, t.fecha_semana.isoformat(), t.indice, t.region, int(t.es_simulado)])
            n += 1
    return n


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--salida", type=Path, default=SALIDA)
    args = p.parse_args()
    print(f"{exportar(args.salida)} filas → {args.salida}")
