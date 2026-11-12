"""Liveness vs. readiness, and what an idle deployment must NOT do to the database.

On a serverless PostgreSQL every query costs compute time and resets the scale-to-zero timer, so the
endpoints a platform calls every few seconds, and the engine's alert feed, must stay away from it
while nobody is using the application.
"""
import pytest

from volcano.db import session as db_session
from volcano.engine.alert_feed import AlertFeed
from volcano.gateway import app as gateway
from volcano.models import Alert, Disease, Municipality


def test_live_answers_without_the_database(client, monkeypatch):
    def unreachable(*_args, **_kwargs):
        raise AssertionError("/live must not open a database connection")

    monkeypatch.setattr(gateway.db_engine, "connect", unreachable)
    assert client.get("/live").json() == {"status": "ok"}
    with pytest.raises(AssertionError):  # /health is the readiness check: it does need the database
        client.get("/health")


def test_health_reports_the_database(client):
    assert client.get("/health").json() == {"status": "ok", "database": "ok"}


def test_alert_feed_reads_a_fresh_snapshot_for_the_first_subscriber(db):
    """While nobody is subscribed the feed does not poll, so the snapshot it kept may be hours old:
    the next subscriber must get the alerts as they are now, not as they were."""
    feed = AlertFeed(db_session.SessionLocal, interval_s=3600)  # never polls during the test
    first, initial = feed.subscribe()
    before = {e.alert.id for e in initial}
    feed.unsubscribe(first)

    alert = Alert(municipality_id=db.query(Municipality).first().id, disease_id=db.query(Disease).first().id,
                  year=2019, epi_week=7, risk_level="ORANGE", origin="OBSERVED", message="Mientras nadie miraba",
                  active=True)
    db.add(alert)
    db.commit()
    try:
        second, initial = feed.subscribe()
        assert {e.alert.id for e in initial} == before | {alert.id}
        feed.unsubscribe(second)
    finally:
        feed.stop()
        db.delete(alert)
        db.commit()
