"""Simulated signal generators: valid ranges and lead over the cases."""
import numpy as np

from volcano.seed.generator import generate_pharmacy_reports, generate_trends
from volcano.shared.epi import iter_weeks

WEEKS = list(iter_weeks((2023, 1), (2024, 52)))
# Cases with a clear outbreak in week 30 of 2024
CASES = {k: (60 if k == (2024, 30) else 10) for k in WEEKS}


def test_trends_stay_in_0_100_and_rise_before_the_outbreak():
    rows = generate_trends(cases={"IRA": CASES}, terms={"IRA": ["gripa"]}, since=WEEKS[0], until=WEEKS[-1], seed=1)
    interest = {(r["year"], r["epi_week"]): r["interest"] for r in rows}
    assert all(0 <= v <= 100 for v in interest.values()) and max(interest.values()) == 100
    assert all(r["is_simulated"] and r["source"] == "simulated" for r in rows)
    usual = np.median(list(interest.values()))
    assert interest[(2024, 29)] > 1.5 * usual  # the week before the outbreak already shows more searches


def test_pharmacy_reports_rise_with_the_associated_disease():
    rows = generate_pharmacy_reports(
        pharmacies=[{"id": 1, "municipality_id": 1, "altitude_m": 2500}], cases={1: {"IRA": CASES}},
        categories={"IRA": ["COLD_FLU"]}, since=WEEKS[0], until=WEEKS[-1], seed=3)
    cold_flu = {(r["year"], r["epi_week"]): r["units"] for r in rows if r["category"] == "COLD_FLU"}
    assert {r["category"] for r in rows} >= {"COLD_FLU", "FACE_MASKS", "REPELLENTS"}
    assert all(r["units"] >= 0 for r in rows)
    usual = np.median(list(cold_flu.values()))
    peak = max(cold_flu.get((2024, 29), 0), cold_flu.get((2024, 30), 0))
    assert peak > 1.8 * usual
