"""Generadores de señales simuladas: rangos válidos y adelanto respecto a los casos."""
import numpy as np

from app.core.epi import iterar_semanas
from app.seed.generador import generar_reportes_farmacia, generar_tendencias

SEMANAS = list(iterar_semanas((2023, 1), (2024, 52)))
# Casos con un brote marcado en la semana 30 de 2024
CASOS = {k: (60 if k == (2024, 30) else 10) for k in SEMANAS}


def test_tendencias_entre_0_y_100_y_suben_antes_del_brote():
    filas = generar_tendencias(casos={"IRA": CASOS}, terminos={"IRA": ["gripa"]}, desde=SEMANAS[0], hasta=SEMANAS[-1],
                               semilla=1)
    indices = {(f["anio"], f["semana_epi"]): f["indice"] for f in filas}
    assert all(0 <= v <= 100 for v in indices.values()) and max(indices.values()) == 100
    assert all(f["es_simulado"] and f["fuente"] == "simulado" for f in filas)
    normal = np.median(list(indices.values()))
    assert indices[(2024, 29)] > 1.5 * normal  # la semana previa al brote ya muestra más búsquedas


def test_reportes_farmacia_suben_con_la_enfermedad_asociada():
    filas = generar_reportes_farmacia(
        farmacias=[{"id": 1, "municipio_id": 1, "altitud_m": 2500}], casos={1: {"IRA": CASOS}},
        categorias={"IRA": ["ANTIGRIPALES"]}, desde=SEMANAS[0], hasta=SEMANAS[-1], semilla=3)
    antigripales = {(f["anio"], f["semana_epi"]): f["unidades"] for f in filas if f["categoria"] == "ANTIGRIPALES"}
    assert {f["categoria"] for f in filas} >= {"ANTIGRIPALES", "TAPABOCAS", "REPELENTES"}
    assert all(f["unidades"] >= 0 for f in filas)
    normal = np.median(list(antigripales.values()))
    pico = max(antigripales.get((2024, 29), 0), antigripales.get((2024, 30), 0))
    assert pico > 1.8 * normal
