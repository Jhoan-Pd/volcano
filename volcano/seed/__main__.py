"""Database seed (idempotent).

Usage:
    python -m volcano.seed              # load whatever is missing (safe to repeat; the container runs it on start)
    python -m volcano.seed --reset      # DELETE every row and load again
    python -m volcano.seed --offline    # do not call Open-Meteo (100 % simulated weather, handy without internet)
    python -m volcano.seed --train      # also train the models and generate predictions (≈1 min locally)
"""
import argparse
import csv
import logging
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from sqlalchemy import delete, func, insert, select

from volcano.db.session import SessionLocal
from volcano.models import (
    Alert,
    Disease,
    Municipality,
    OfficialCase,
    Pharmacy,
    PharmacyReport,
    Prediction,
    Role,
    SearchTrend,
    TrainedModel,
    User,
    VolcanicEvent,
    WeatherRecord,
)
from volcano.models.enums import RoleName, VolcanicEventType, VolcanoLevel
from volcano.seed import catalog
from volcano.seed.generator import (
    generate_cases,
    generate_pharmacy_reports,
    generate_trends,
    simulate_weather,
    weekly_weather,
)
from volcano.shared.config import settings
from volcano.shared.epi import EpiWeek, iter_weeks, last_complete_week, week_of, week_start
from volcano.shared.security import hash_password
from volcano.sources import DataSourceError, OpenMeteoSource

log = logging.getLogger("seed")
DATA = Path(__file__).parent / "data"
SEED = 42
ASH_LABELS_ES = {1: "leve", 2: "moderada", 3: "fuerte"}


def _has_rows(db, model) -> bool:
    return (db.scalar(select(func.count()).select_from(model)) or 0) > 0


def reset(db) -> None:
    for model in (Alert, Prediction, TrainedModel, PharmacyReport, Pharmacy, OfficialCase,
                  SearchTrend, WeatherRecord, VolcanicEvent, User, Disease, Municipality, Role):
        db.execute(delete(model))
    db.commit()
    log.info("Data deleted")


def seed_roles_and_users(db) -> None:
    if not _has_rows(db, Role):
        db.add_all([
            Role(name=RoleName.ADMIN, description="Administra catálogos, usuarios, eventos y el modelo"),
            Role(name=RoleName.PHARMACY, description="Reporta ventas semanales de su farmacia"),
            Role(name=RoleName.CITIZEN, description="Consulta el dashboard y recibe alertas"),
        ])
        db.commit()
    roles = {r.name: r.id for r in db.scalars(select(Role))}
    pasto = db.scalar(select(Municipality.id).where(Municipality.divipola_code == "52001"))
    users = [
        (settings.ADMIN_NAME, settings.ADMIN_EMAIL, settings.ADMIN_PASSWORD, RoleName.ADMIN),
        ("Farmacia Demo Centro", "farmacia@demo.co", settings.DEMO_PASSWORD, RoleName.PHARMACY),
        ("Ciudadano Demo", "ciudadano@demo.co", settings.DEMO_PASSWORD, RoleName.CITIZEN),
    ]
    for name, email, password, role in users:
        if db.scalar(select(User).where(User.email == email.lower())) is None:
            db.add(User(name=name, email=email.lower(), password_hash=hash_password(password),
                        role_id=roles[role], municipality_id=pasto))
    db.commit()


def seed_catalogs(db) -> None:
    if not _has_rows(db, Municipality):
        db.add_all([Municipality(department="Nariño", **m) for m in catalog.MUNICIPALITIES])
    if not _has_rows(db, Disease):
        db.add_all([Disease(**d) for d in catalog.DISEASES])
    db.commit()


def seed_pharmacies(db) -> None:
    if _has_rows(db, Pharmacy):
        return
    municipalities = {m.name: m for m in db.scalars(select(Municipality))}
    pharmacy_user = db.scalar(select(User).where(User.email == "farmacia@demo.co"))
    for i, (name, town) in enumerate(catalog.PHARMACIES):
        m = municipalities[town]
        db.add(Pharmacy(
            name=name, tax_id=f"90{i:07d}-{i % 10}", address=f"Calle {10 + i} # {5 + i}-{20 + i}, {town}",
            phone=f"602 7{i:02d} 0000", municipality_id=m.id,
            user_id=pharmacy_user.id if i == 0 and pharmacy_user else None,
            latitude=m.latitude + 0.002 * (i % 3), longitude=m.longitude - 0.002 * (i % 2),
        ))
    db.commit()


def seed_weather(db, online: bool, return_rows: bool = True) -> dict[int, list[dict]]:
    """Load the weather when missing. With `return_rows`, return each municipality's daily weather
    (used to generate the cases)."""
    today = date.today()
    since = date(settings.SEED_START_YEAR, 1, 1) - timedelta(days=60)  # margin for the lags
    municipalities = list(db.scalars(select(Municipality).order_by(Municipality.id)))
    if _has_rows(db, WeatherRecord):
        log.info("Weather already loaded; reusing it")
        if not return_rows:
            return {}
        fields = ("date", "temp_mean_c", "relative_humidity_pct", "precipitation_mm", "is_forecast")
        return {m.id: [{f: getattr(r, f) for f in fields}
                       for r in db.scalars(select(WeatherRecord).where(WeatherRecord.municipality_id == m.id))]
                for m in municipalities}

    source = OpenMeteoSource()
    out = {}
    for m in municipalities:
        rows: list[dict] = []
        if online and settings.SEED_REAL_WEATHER:
            try:
                t0 = time.time()
                rows = source.fetch(latitude=m.latitude, longitude=m.longitude, mode="history",
                                    since=since, until=today - timedelta(days=1))
                recent = source.fetch(latitude=m.latitude, longitude=m.longitude, mode="forecast", past_days=10)
                by_date = {r["date"]: r for r in rows}
                by_date.update({r["date"]: r for r in recent})
                rows = sorted(by_date.values(), key=lambda r: r["date"])
                log.info("REAL Open-Meteo weather %s: %d days (%.1fs)", m.name, len(rows), time.time() - t0)
            except DataSourceError as exc:
                log.warning("Open-Meteo unavailable for %s (%s): using simulated weather", m.name, exc)
                rows = []
        if not rows:
            rows = simulate_weather({"altitude_m": m.altitude_m}, since, today + timedelta(days=15), today,
                                    SEED + int(m.divipola_code))
        db.execute(insert(WeatherRecord), [{**r, "municipality_id": m.id} for r in rows])
        db.commit()
        out[m.id] = rows
    return out


def _so2_history() -> dict[EpiWeek, float]:
    with open(DATA / "galeras_weekly_so2.csv", encoding="utf-8") as fh:
        return {(int(r["year"]), int(r["epi_week"])): float(r["so2_tons_per_day"]) for r in csv.DictReader(fh)}


def seed_volcano(db) -> tuple[dict[EpiWeek, float], dict[int, dict[EpiWeek, int]]]:
    """Weekly bulletins + ash falls. Returns weekly SO₂ and ash per municipality (for the cases)."""
    rng = np.random.default_rng(SEED)
    so2 = _so2_history()
    # Extend the series through 2025-2026 with values in the same range (simulated)
    for y, w in iter_weeks((2025, 1), last_complete_week()):
        so2.setdefault((y, w), round(float(np.clip(rng.normal(380, 120), 90, 900)), 1))

    municipalities = {m.name: m.id for m in db.scalars(select(Municipality))}
    ash: dict[int, dict[EpiWeek, int]] = {mid: {} for mid in municipalities.values()}
    for day, names, intensity in catalog.SIMULATED_ASH_FALLS:
        k = week_of(date.fromisoformat(day))
        for n in names:
            ash[municipalities[n]][k] = max(ash[municipalities[n]].get(k, 0), intensity)

    if _has_rows(db, VolcanicEvent):
        return so2, ash

    real_start = date.fromisoformat(catalog.REAL_BULLETIN["start_date"])
    rows = []
    for (y, w), v in sorted(so2.items()):
        start = week_start(y, w)
        if start >= real_start - timedelta(days=3):
            break
        # Galeras stayed on the SGC's Yellow Alert during this period; the SO₂ is estimated
        rows.append({"event_type": VolcanicEventType.BULLETIN, "activity_level": VolcanoLevel.YELLOW,
                     "start_date": start, "end_date": start + timedelta(days=6), "so2_tons_per_day": v,
                     "ash_intensity": 0, "description": "Boletín semanal (SO₂ estimado, dato simulado para la semilla)",
                     "is_simulated": True})
    rows.append({"event_type": VolcanicEventType.BULLETIN, "activity_level": catalog.REAL_BULLETIN["activity_level"],
                 "start_date": real_start, "end_date": date.fromisoformat(catalog.REAL_BULLETIN["end_date"]),
                 "description": catalog.REAL_BULLETIN["description"],
                 "bulletin_url": catalog.REAL_BULLETIN["bulletin_url"], "ash_intensity": 0, "is_simulated": False})
    rows.extend(
        {"event_type": VolcanicEventType.ASH_FALL, "activity_level": VolcanoLevel.YELLOW,
         "start_date": date.fromisoformat(day), "end_date": date.fromisoformat(day) + timedelta(days=1),
         "municipality_id": municipalities[n], "ash_intensity": intensity,
         "description": f"Caída de ceniza {ASH_LABELS_ES[intensity]} (evento simulado para la semilla)",
         "is_simulated": True}
        for day, names, intensity in catalog.SIMULATED_ASH_FALLS for n in names)
    db.execute(insert(VolcanicEvent), rows)
    db.commit()
    return so2, ash


def seed_cases(db, weather: dict[int, list[dict]], so2, ash) -> None:
    if _has_rows(db, OfficialCase):
        return
    diseases = {d.code: d.id for d in db.scalars(select(Disease))}
    end = last_complete_week()
    total = 0
    for m in db.scalars(select(Municipality).order_by(Municipality.id)):
        baseline = catalog.WEEKLY_BASELINE.get(m.name) or {k: 1.0 for k in diseases}
        series = generate_cases(
            municipality=m.name, population=m.population, baseline=baseline, weather=weekly_weather(weather[m.id]),
            so2=so2, ash=ash.get(m.id, {}), since=(settings.SEED_START_YEAR, 1), until=end,
            seed=SEED + int(m.divipola_code),
        )
        rows = [{"municipality_id": m.id, "disease_id": diseases[code], "year": y, "epi_week": w, "cases": c,
                 "source": "SIVIGILA (simulated)", "is_simulated": True}
                for code, points in series.items() if code in diseases for y, w, c in points]
        db.execute(insert(OfficialCase), rows)
        db.commit()
        total += len(rows)
    log.info("Weekly cases generated: %d", total)


def _cases_by_municipality(db) -> dict[int, dict[str, dict[EpiWeek, int]]]:
    codes = {d.id: d.code for d in db.scalars(select(Disease))}
    out: dict[int, dict[str, dict[EpiWeek, int]]] = {}
    for mid, did, y, w, c in db.execute(select(OfficialCase.municipality_id, OfficialCase.disease_id,
                                               OfficialCase.year, OfficialCase.epi_week, OfficialCase.cases)):
        out.setdefault(mid, {}).setdefault(codes[did], {})[(y, w)] = c
    return out


def seed_trends(db) -> None:
    """Simulated searches (Google Trends CO-NAR) consistent with the cases already loaded."""
    if _has_rows(db, SearchTrend) or not _has_rows(db, OfficialCase):
        return
    department: dict[str, dict[EpiWeek, int]] = {}
    for series in _cases_by_municipality(db).values():
        for code, s in series.items():
            target = department.setdefault(code, {})
            for k, v in s.items():
                target[k] = target.get(k, 0) + v
    terms = {d.code: d.search_term_list for d in db.scalars(select(Disease))}
    rows = generate_trends(cases=department, terms=terms, since=(settings.SEED_START_YEAR, 1),
                           until=last_complete_week(), seed=SEED + 7)
    db.execute(insert(SearchTrend), rows)
    db.commit()
    log.info("Simulated searches: %d term-weeks", len(rows))


def seed_pharmacy_reports(db) -> None:
    """Simulated weekly sales of the demo pharmacies, consistent with their municipality's cases."""
    if _has_rows(db, PharmacyReport) or not _has_rows(db, OfficialCase):
        return
    altitudes = {m.id: m.altitude_m for m in db.scalars(select(Municipality))}
    pharmacies = [{"id": p.id, "municipality_id": p.municipality_id, "altitude_m": altitudes.get(p.municipality_id)}
                  for p in db.scalars(select(Pharmacy).order_by(Pharmacy.id))]
    categories = {d.code: d.pharmacy_category_list for d in db.scalars(select(Disease))}
    rows = generate_pharmacy_reports(pharmacies=pharmacies, cases=_cases_by_municipality(db), categories=categories,
                                     since=(settings.SEED_START_YEAR, 1), until=last_complete_week(), seed=SEED + 11)
    for i in range(0, len(rows), 5000):
        db.execute(insert(PharmacyReport), rows[i:i + 5000])
    db.commit()
    log.info("Simulated pharmacy reports: %d rows", len(rows))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Load the initial data")
    parser.add_argument("--reset", action="store_true", help="delete every row before loading")
    parser.add_argument("--offline", action="store_true", help="do not call Open-Meteo")
    parser.add_argument("--train", action="store_true", help="train the models and generate predictions")
    args = parser.parse_args()

    t0 = time.time()
    with SessionLocal() as db:
        if args.reset:
            reset(db)
        seed_catalogs(db)
        seed_roles_and_users(db)
        seed_pharmacies(db)
        cases_missing = not _has_rows(db, OfficialCase)
        weather = seed_weather(db, online=not args.offline, return_rows=cases_missing)
        so2, ash = seed_volcano(db)
        if cases_missing:
            seed_cases(db, weather, so2, ash)
        seed_trends(db)
        seed_pharmacy_reports(db)
        if args.train:
            from volcano.services.alerts import AlertService  # noqa: PLC0415 - only needed with --train
            from volcano.services.forecasting import ForecastingService  # noqa: PLC0415

            models, errors = ForecastingService(db).train()
            log.info("Models trained: %d %s", len(models), errors or "")
            log.info("Alerts: %s", AlertService(db).evaluate(send_email=False))
    log.info("Seed finished in %.1fs", time.time() - t0)


if __name__ == "__main__":
    main()
