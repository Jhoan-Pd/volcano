"""Epidemiological week helpers.

Colombia (INS/SIVIGILA) uses epidemiological weeks that start on Sunday, like the MMWR
calendar; some years have a week 53. The `epiweeks` library implements that calendar, so
nothing here assumes "52 fixed weeks".
"""
from collections.abc import Iterator
from datetime import date, timedelta

from epiweeks import Week, Year

EpiWeek = tuple[int, int]  # (year, week)


def week_of(day: date) -> EpiWeek:
    w = Week.fromdate(day)
    return w.year, w.week


def week_start(year: int, week: int) -> date:
    return Week(year, week).startdate()


def weeks_in_year(year: int) -> int:
    return Year(year).totalweeks()


def last_complete_week(today: date | None = None) -> EpiWeek:
    today = today or date.today()
    w = Week.fromdate(today) - 1
    return w.year, w.week


def iter_weeks(start: EpiWeek, end: EpiWeek) -> Iterator[EpiWeek]:
    w = Week(*start)
    last = Week(*end)
    while w <= last:
        yield w.year, w.week
        w = w + 1


def shift(year: int, week: int, n: int) -> EpiWeek:
    w = Week(year, week) + n
    return w.year, w.week


def label(year: int, week: int) -> str:
    """Week label shown in the UI, e.g. ``2026-S14`` (S = «semana»)."""
    return f"{year}-S{week:02d}"


def date_range(year: int, week: int) -> tuple[date, date]:
    start = week_start(year, week)
    return start, start + timedelta(days=6)
