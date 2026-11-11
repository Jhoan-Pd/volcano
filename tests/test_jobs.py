"""Daily update (GitHub Actions cron) without touching the internet or a real engine."""
from datetime import date

import httpx
import pytest

from volcano.rpc.client import EngineSyncClient
from volcano.schemas.engine import RefreshResultOut
from volcano.schemas.model import TrainingStatus
from volcano.services import training
from volcano.services.daily_update import DailyUpdateService

CRON = {"X-Cron-Secret": "test-cron"}


@pytest.fixture
def fake_sources(monkeypatch):
    """Replace the external sources and the engine: weather answers, Trends fails."""
    from volcano.schemas.weather import WeatherSyncResult
    from volcano.services.search_trends import SearchTrendService
    from volcano.services.sivigila import SivigilaService
    from volcano.services.weather import WeatherService

    calls = []

    def weather(self, past_days=14):
        calls.append("weather")
        return WeatherSyncResult(municipalities=6, saved_rows=180, errors=[])

    def trends(self, force=False, since=None):
        calls.append("trends")
        raise RuntimeError("Google answered 429")

    def sivigila(self, since_year=None):
        calls.append("sivigila")
        return {"saved_rows": 0}

    def refresh(self, evaluate_alerts=True, send_email=True):
        calls.append("refresh")
        return RefreshResultOut(predictions=96, alerts_new=1, alerts_updated=0, alerts_closed=0, alerts_active=1,
                                emails_sent=0)

    def start_training(self, disease_id=None):
        calls.append("start_training")
        return TrainingStatus(running=True)

    monkeypatch.setattr(WeatherService, "sync", weather)
    monkeypatch.setattr(SearchTrendService, "sync", trends)
    monkeypatch.setattr(SivigilaService, "sync", sivigila)
    monkeypatch.setattr(EngineSyncClient, "refresh_forecasts", refresh)
    monkeypatch.setattr(EngineSyncClient, "start_training", start_training)
    return calls


def test_cron_requires_its_secret(client):
    assert client.post("/api/v1/jobs/daily-update").status_code == 401
    assert client.post("/api/v1/jobs/daily-update", headers={"X-Cron-Secret": "other"}).status_code == 401


def test_a_failed_step_does_not_stop_the_others(client, fake_sources):
    r = client.post("/api/v1/jobs/daily-update", headers=CRON, params={"sivigila": "no", "retrain": "no"})
    assert r.status_code == 200, r.text
    steps = {s["step"]: s for s in r.json()["steps"]}
    assert steps["weather"]["ok"] and steps["weather"]["result"]["saved_rows"] == 180
    assert not steps["trends"]["ok"] and "429" in steps["trends"]["error"]
    assert steps["forecasts_and_alerts"]["ok"] and steps["forecasts_and_alerts"]["result"]["predictions"] == 96
    assert "sivigila" not in steps and r.json()["ok"] is False


def test_on_mondays_sivigila_is_downloaded_and_the_engine_retrains(db, fake_sources):
    monday = date(2026, 10, 5)
    result = DailyUpdateService(db, today=monday).run()
    assert [s["step"] for s in result["steps"]] == ["weather", "trends", "sivigila", "retrain"]
    assert "start_training" in fake_sources and "refresh" not in fake_sources

    tuesday = date(2026, 10, 6)
    steps = [s["step"] for s in DailyUpdateService(db, today=tuesday).run(retrain="no")["steps"]]
    assert steps == ["weather", "trends", "forecasts_and_alerts", "frontend"]


def test_engine_down_is_reported_as_a_failed_step(db, fake_sources, monkeypatch):
    from volcano.shared.errors import ServiceUnavailableError

    def down(self, evaluate_alerts=True, send_email=True):
        raise ServiceUnavailableError("El motor de predicción no está disponible")

    monkeypatch.setattr(EngineSyncClient, "refresh_forecasts", down)
    steps = {s["step"]: s for s in DailyUpdateService(db, today=date(2026, 10, 6)).run(retrain="no")["steps"]}
    assert not steps["forecasts_and_alerts"]["ok"] and steps["weather"]["ok"]


def test_training_control_prevents_two_runs_at_once():
    from volcano.shared.errors import ConflictError

    control = training.TrainingControl()
    assert control.start().running
    with pytest.raises(ConflictError):
        control.start()
    control.finish("listo", ["IRA: sin datos"])
    status = control.status()
    assert not status.running and status.message == "listo" and status.errors == ["IRA: sin datos"]
    assert status.started_at is not None and status.finished_at >= status.started_at


def test_frontend_revalidation_is_optional_and_never_raises(monkeypatch):
    from volcano.notifications import frontend
    from volcano.shared.config import settings

    monkeypatch.setattr(settings, "REVALIDATE_SECRET", None)
    assert frontend.revalidate_frontend()["revalidated"] is False

    calls = []

    def fake_post(url, headers, timeout):
        calls.append((url, headers["Authorization"]))
        return httpx.Response(200, json={"paths": ["/"]}, request=httpx.Request("POST", url))

    monkeypatch.setattr(settings, "REVALIDATE_SECRET", "s3cret")
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://front.test/")
    monkeypatch.setattr(frontend.httpx, "post", fake_post)
    assert frontend.revalidate_frontend() == {"revalidated": True, "paths": ["/"]}
    assert calls == [("https://front.test/api/revalidate", "Bearer s3cret")]

    def failing_post(url, headers, timeout):
        raise httpx.ConnectError("no network")

    monkeypatch.setattr(frontend.httpx, "post", failing_post)
    assert frontend.revalidate_frontend()["revalidated"] is False  # a frontend outage never breaks the cron job


def test_realtime_publisher_never_raises(monkeypatch):
    from volcano.notifications import realtime

    sent = []

    def fake_post(url, json, headers, timeout):
        sent.append((url, json["event"], headers[realtime.INTERNAL_HEADER]))
        return httpx.Response(202, json={"delivered": 3}, request=httpx.Request("POST", url))

    monkeypatch.setattr(realtime.httpx, "post", fake_post)
    assert realtime.publish_event("data.updated") is True
    assert sent[0][0].endswith("/internal/events") and sent[0][1] == "data.updated"

    def failing_post(*_, **__):
        raise httpx.ConnectError("hub down")

    monkeypatch.setattr(realtime.httpx, "post", failing_post)
    assert realtime.publish_event("data.updated") is False
