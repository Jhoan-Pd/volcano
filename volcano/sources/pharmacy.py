"""Pharmacy sales index as a model input.

There is no public dataset of medicine sales per municipality, so the "source" is the weekly
reports filed by the registered pharmacies (pharmacy_reports table). This adapter turns them into
a signal that is comparable across municipalities:

    units_per_pharmacy = category units / pharmacies that reported that week
    sales_index = units_per_pharmacy / average of the previous 52 weeks × 100

An index of 140 means "40 % more sales than usual". Dividing by the pharmacies that reported
keeps a new pharmacy (or one that skipped a week) from looking like an outbreak.

Plain Python on purpose: the gateway serves the public index and does not need pandas for it.
"""
from collections import defaultdict
from collections.abc import Iterable
from datetime import date
from typing import Any

from sqlalchemy import select

from volcano.models import Pharmacy, PharmacyReport
from volcano.shared.epi import week_start
from volcano.sources.base import DataSource

BASELINE_WEEKS = 52
MIN_BASELINE_WEEKS = 4


def compute_index(reports: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Weekly index per municipality and category from raw report rows
    (municipality_id, pharmacy_id, year, epi_week, category, units)."""
    totals: dict[tuple, int] = defaultdict(int)
    reporting: dict[tuple, set[int]] = defaultdict(set)
    for r in reports:
        key = (r["municipality_id"], r["category"], r["year"], r["epi_week"])
        totals[key] += r["units"]
        reporting[key].add(r["pharmacy_id"])

    series: dict[tuple, list[tuple]] = defaultdict(list)
    for (mid, category, year, week), units in totals.items():
        series[(mid, category)].append((year, week, units, len(reporting[(mid, category, year, week)])))

    out = []
    for (mid, category), weeks in sorted(series.items()):
        weeks.sort()
        per_pharmacy = [units / n for _, _, units, n in weeks]
        for i, (year, week, units, n) in enumerate(weeks):
            previous = per_pharmacy[max(0, i - BASELINE_WEEKS):i]  # never the current week
            baseline = sum(previous) / len(previous) if len(previous) >= MIN_BASELINE_WEEKS else None
            index = round(per_pharmacy[i] / baseline * 100, 1) if baseline else None
            out.append({"municipality_id": mid, "year": year, "epi_week": week, "category": category,
                        "units": units, "reporting_pharmacies": n, "sales_index": index})
    return out


class PharmacySource(DataSource):
    name = "pharmacies"

    def __init__(self, db):
        self.db = db

    def _reports(self, municipality_id: int | None, categories: list[str] | None) -> list[dict[str, Any]]:
        stmt = (select(Pharmacy.municipality_id, PharmacyReport.pharmacy_id, PharmacyReport.year,
                       PharmacyReport.epi_week, PharmacyReport.category, PharmacyReport.units)
                .join(Pharmacy, Pharmacy.id == PharmacyReport.pharmacy_id))
        if municipality_id is not None:
            stmt = stmt.where(Pharmacy.municipality_id == municipality_id)
        if categories:
            stmt = stmt.where(PharmacyReport.category.in_(categories))
        return [dict(row) for row in self.db.execute(stmt).mappings()]

    def fetch(self, *, municipality_id: int | None = None, categories: list[str] | None = None,
              since: date | None = None, **_: Any) -> list[dict[str, Any]]:
        rows = compute_index(self._reports(municipality_id, categories))
        if since:
            rows = [r for r in rows if week_start(r["year"], r["epi_week"]) >= since]
        return rows

    def check(self) -> None:
        self.db.execute(select(PharmacyReport.id).limit(1))
