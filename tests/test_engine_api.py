"""Gateway REST → gRPC bridge: JSON (unary), SSE (server streaming) and row upload (client streaming),
against the real gRPC test server."""
import json

import pytest

from tests.conftest import ENGINE_TOKEN
from volcano.gateway.app import app
from volcano.models import Municipality
from volcano.rpc.client import EngineClient, engine_client
from volcano.services.training import control

URL = "/api/v1/engine"


@pytest.fixture
def engine_down():
    app.dependency_overrides[engine_client] = lambda: EngineClient("127.0.0.1:1", ENGINE_TOKEN, timeout_s=2)
    yield
    app.dependency_overrides.pop(engine_client, None)


def _sse_events(lines) -> list[tuple[str, dict]]:
    events, name = [], "message"
    for line in lines:
        if line.startswith("event: "):
            name = line.removeprefix("event: ")
        elif line.startswith("data: "):
            events.append((name, json.loads(line.removeprefix("data: "))))
            name = "message"
    return events


def test_status_and_forecast(client, db, engine_client_override, trained_ira):
    s = client.get(f"{URL}/status").json()
    assert s["available"] and s["latency_ms"] is not None

    pasto = db.query(Municipality).filter_by(divipola_code="52001").one().id
    r = client.get(f"{URL}/forecast", params={"municipality_id": pasto, "disease_id": trained_ira})
    assert r.status_code == 200, r.text
    data = r.json()
    assert [p["horizon"] for p in data["points"]] == [1, 2, 3, 4]
    assert data["points"][0]["level"] in ("GREEN", "YELLOW", "ORANGE", "RED")

    r = client.get(f"{URL}/forecast", params={"municipality_id": 9999, "disease_id": trained_ira})
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"


def test_engine_down_answers_503_without_taking_the_api_down(client, engine_down):
    assert client.get(f"{URL}/status").json()["available"] is False
    r = client.get(f"{URL}/forecast", params={"municipality_id": 1, "disease_id": 1})
    assert r.status_code == 503 and r.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert client.get("/health").status_code == 200
    services = client.get("/health/services").json()
    assert services["gateway"]["available"] and not services["engine"]["available"]
    assert services["realtime"]["available"] is False


def test_training_over_sse_is_admin_only(client, engine_client_override, trained_ira, admin_headers,
                                         citizen_headers):
    assert client.post(f"{URL}/training", headers=citizen_headers).status_code == 403
    control.reset()
    with client.stream("POST", f"{URL}/training", params={"disease_id": trained_ira}, headers=admin_headers) as r:
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
        events = _sse_events(r.iter_lines())
    assert {n for n, _ in events} == {"progress"}
    assert events[0][1]["stage"] == "STARTED" and events[-1][1]["stage"] == "FINISHED"
    assert events[-1][1]["percent"] == 100


def test_training_in_progress_is_409_before_the_stream_opens(client, engine_client_override, admin_headers):
    control.start()
    try:
        r = client.post(f"{URL}/training", headers=admin_headers)
        assert r.status_code == 409 and r.json()["error"]["code"] == "CONFLICT"
        r = client.post("/api/v1/model/retrain", headers=admin_headers)
        assert r.status_code == 409
        assert client.get("/api/v1/model/status", headers=admin_headers).json()["running"] is True
    finally:
        control.reset()


def test_model_predict_goes_through_the_engine(client, engine_client_override, trained_ira, admin_headers):
    r = client.post("/api/v1/model/predict", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["predictions"] >= 8


def test_pharmacy_upload_over_client_streaming(client, engine_client_override, pharmacy_headers, citizen_headers):
    body = {"rows": [{"row": 2, "year": 2024, "epi_week": 5, "category": "COLD_FLU", "units": 10},
                     {"row": 3, "year": 2024, "epi_week": 5, "category": "NOTHING", "units": 10}]}
    assert client.post(f"{URL}/pharmacy-upload", json=body, headers=citizen_headers).status_code == 403
    r = client.post(f"{URL}/pharmacy-upload", json=body, headers=pharmacy_headers)
    assert r.status_code == 200, r.text
    summary = r.json()
    assert summary["rows_received"] == 2 and summary["rows_rejected"] == 1
    assert summary["weeks_rejected"] == 1  # week outside the pharmacy's 8-week window
    assert client.post(f"{URL}/pharmacy-upload", json={"rows": []}, headers=pharmacy_headers).status_code == 422
