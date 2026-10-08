"""Utilidades de semana epidemiológica.

Colombia (INS/SIVIGILA) usa semanas epidemiológicas que inician en domingo, igual que
el calendario MMWR; algunos años tienen semana 53. La librería `epiweeks` implementa
ese calendario, así que no se asume "52 semanas fijas" como en el sistema anterior.
"""
from datetime import date, timedelta

from epiweeks import Week, Year


def semana_de(fecha: date) -> tuple[int, int]:
    w = Week.fromdate(fecha)
    return w.year, w.week


def inicio_semana(anio: int, semana: int) -> date:
    return Week(anio, semana).startdate()


def semanas_del_anio(anio: int) -> int:
    return Year(anio).totalweeks()


def ultima_semana_completa(hoy: date | None = None) -> tuple[int, int]:
    hoy = hoy or date.today()
    w = Week.fromdate(hoy) - 1
    return w.year, w.week


def iterar_semanas(desde: tuple[int, int], hasta: tuple[int, int]):
    w = Week(*desde)
    fin = Week(*hasta)
    while w <= fin:
        yield w.year, w.week
        w = w + 1


def desplazar(anio: int, semana: int, n: int) -> tuple[int, int]:
    w = Week(anio, semana) + n
    return w.year, w.week


def etiqueta(anio: int, semana: int) -> str:
    return f"{anio}-S{semana:02d}"


def rango_fechas(anio: int, semana: int) -> tuple[date, date]:
    ini = inicio_semana(anio, semana)
    return ini, ini + timedelta(days=6)
