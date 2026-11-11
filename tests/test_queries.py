"""Data structures and query counts: guard against performance regressions (N+1)."""
from contextlib import contextmanager
from datetime import date

from sqlalchemy import event

from volcano.db.session import engine
from volcano.models import Disease, Municipality, OfficialCase, WeatherRecord
from volcano.repositories.domain import WeatherRecordRepository


@contextmanager
def count_queries():
    counter = {"n": 0}

    def _count(*_):
        counter["n"] += 1

    event.listen(engine, "before_cursor_execute", _count)
    try:
        yield counter
    finally:
        event.remove(engine, "before_cursor_execute", _count)


def test_generic_upsert_inserts_and_updates_with_one_read(db):
    repo = WeatherRecordRepository(db)
    rows = [{"municipality_id": 1, "date": date(2018, 1, d), "temp_mean_c": 12.0} for d in (1, 2, 3)]
    key = ("municipality_id", "date")
    scope = [WeatherRecord.date.in_([r["date"] for r in rows])]
    assert repo.upsert(rows, key, scope) == (3, 0)
    rows[0]["temp_mean_c"] = 15.5
    with count_queries() as c:
        assert repo.upsert(rows, key, scope) == (0, 3)
    # 1 SELECT of the existing rows + the commit's writes; never one read per row
    assert c["n"] <= 3
    assert db.query(WeatherRecord).filter_by(municipality_id=1, date=date(2018, 1, 1)).one().temp_mean_c == 15.5


def test_municipality_risk_is_not_one_query_per_municipality(client, db):
    if db.query(OfficialCase).count() == 0:  # this test can run alone: create a minimal series
        for m in db.query(Municipality):
            for d in db.query(Disease):
                db.add_all(OfficialCase(municipality_id=m.id, disease_id=d.id, year=2014, epi_week=w, cases=w % 5)
                           for w in range(1, 20))
        db.commit()
    with count_queries() as c:
        r = client.get("/api/v1/dashboard/municipality-risk")
    assert r.status_code == 200
    municipalities, diseases = len(r.json()), 4
    # Before: ~3 queries per (municipality × disease). Now: a few per disease.
    assert c["n"] < municipalities * diseases
