"""Realtime hub: fan-out, slow consumers, the alert relay, and the WebSocket protocol end to end
(WebSocket → hub → gRPC engine → test database)."""
import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from tests.conftest import ENGINE_TOKEN
from volcano.models import Alert, Municipality
from volcano.realtime import app as realtime
from volcano.realtime.alert_relay import AlertRelay
from volcano.realtime.hub import OUTBOUND_QUEUE_SIZE, Client, ConnectionHub
from volcano.rpc.client import EngineClient
from volcano.shared.config import settings


class FakeSocket:
    """Enough of a WebSocket for the hub: it records what would be sent."""

    def __init__(self):
        self.sent = []


def _client(**kwargs) -> Client:
    return Client(FakeSocket(), **kwargs)


def _drain(client: Client) -> list[dict]:
    out = []
    while not client.outbox.empty():
        item = client.outbox.get_nowait()
        if item is not None:
            out.append(item)
    return out


def _alert(alert_id: int, municipality_id: int = 1, level: str = "ORANGE") -> dict:
    return {"id": alert_id, "municipality_id": municipality_id, "municipality": "Pasto", "disease_id": 1,
            "disease": "Gripe", "week": "2026-S10", "level": level, "origin": "OBSERVED", "message": "x"}


# ── hub ──────────────────────────────────────────────────────────────────────
def test_broadcast_reaches_matching_clients_and_announces_presence():
    hub = ConnectionHub()
    a, b = _client(alerts=True), _client()
    hub.add(a)
    hub.add(b)
    assert _drain(a)[-1] == {"type": "presence", "online": 2}
    _drain(b)
    assert hub.broadcast({"type": "x"}, to=lambda c: c.alerts) == 1
    assert _drain(a) == [{"type": "x"}] and _drain(b) == []
    hub.remove(b)
    assert _drain(a) == [{"type": "presence", "online": 1}]


def test_a_slow_client_is_dropped_without_blocking_the_others():
    hub = ConnectionHub()
    slow, fast = _client(), _client()
    hub.add(slow)
    hub.add(fast)
    for i in range(OUTBOUND_QUEUE_SIZE + 5):
        hub.broadcast({"type": "tick", "n": i})
        _drain(fast)  # the fast client keeps reading
    assert slow.closing and len(hub) == 1
    assert not fast.closing


def test_connection_limit():
    hub = ConnectionHub(max_connections=1)
    hub.add(_client())
    assert hub.full


# ── alert relay ──────────────────────────────────────────────────────────────
def test_relay_replay_rebuilds_the_snapshot_and_announces_what_changed():
    hub = ConnectionHub()
    relay = AlertRelay(hub, engine=None)
    watcher = _client(alerts=True)
    hub.add(watcher)
    relay.active = {1: _alert(1), 2: _alert(2)}  # what the relay knew before losing the stream

    for event in ({"kind": "ACTIVE", "at": "t", "alert": _alert(1)},
                  {"kind": "ACTIVE", "at": "t", "alert": _alert(3, level="RED")},
                  {"kind": "SYNCED", "at": "t", "alert": {}}):
        relay.handle(event)

    assert relay.connected and set(relay.active) == {1, 3}
    sent = [m for m in _drain(watcher) if m["type"] == "alert"]
    assert {(m["event"]["kind"], m["event"]["alert"]["id"]) for m in sent} == {("CLOSED", 2), ("CREATED", 3)}


def test_relay_filters_by_municipality_and_tracks_changes():
    hub = ConnectionHub()
    relay = AlertRelay(hub, engine=None)
    pasto, consaca = _client(alerts=True, alerts_municipality_id=1), _client(alerts=True, alerts_municipality_id=2)
    hub.add(pasto)
    hub.add(consaca)
    relay.handle({"kind": "SYNCED", "at": "t", "alert": {}})
    relay.handle({"kind": "CREATED", "at": "t", "alert": _alert(7, municipality_id=2)})
    assert [m["type"] for m in _drain(consaca) if m["type"] == "alert"] == ["alert"]
    assert not [m for m in _drain(pasto) if m["type"] == "alert"]
    relay.handle({"kind": "CLOSED", "at": "t", "alert": _alert(7, municipality_id=2)})
    assert relay.snapshot() == []


def test_origin_check():
    assert realtime.origin_allowed(None)
    assert realtime.origin_allowed(settings.cors_origins[0])
    assert not realtime.origin_allowed("https://evil.example")


# ── end to end ───────────────────────────────────────────────────────────────
@pytest.fixture
def hub_client(grpc_engine, monkeypatch):
    monkeypatch.setattr(realtime, "engine", lambda: EngineClient(f"127.0.0.1:{grpc_engine.port}", ENGINE_TOKEN))
    with TestClient(realtime.app) as c:
        deadline = time.monotonic() + 10
        while c.get("/realtime/health").json()["alerts_upstream"] != "connected" and time.monotonic() < deadline:
            time.sleep(0.1)
        yield c


def _receive_until(ws, kind: str, limit: int = 50) -> dict:
    for _ in range(limit):
        msg = ws.receive_json()
        if msg["type"] == kind:
            return msg
    raise AssertionError(f"no {kind} message")


def test_websocket_protocol_end_to_end(hub_client, db, trained_ira):
    pasto = db.query(Municipality).filter_by(divipola_code="52001").one().id
    assert hub_client.get("/realtime/health").json()["alerts_upstream"] == "connected"
    with hub_client.websocket_connect("/ws") as ws:
        welcome = ws.receive_json()
        assert welcome["type"] == "welcome" and welcome["protocol"] == 1 and welcome["client_id"]

        ws.send_json({"type": "ping"})
        assert _receive_until(ws, "pong") == {"type": "pong"}

        ws.send_json({"type": "subscribe", "channel": "alerts", "municipality_id": pasto})
        snapshot = _receive_until(ws, "alerts.snapshot")
        assert snapshot["upstream"] == "connected" and isinstance(snapshot["alerts"], list)

        ws.send_json({"type": "simulate", "scenario": {"id": "s1", "municipality_id": pasto,
                                                        "disease_id": trained_ira, "rain_change_pct": 80}})
        result = _receive_until(ws, "simulation.result")["result"]
        assert result["id"] == "s1" and result["error"] is None and len(result["scenario"]) == 4

        ws.send_json({"type": "simulate", "scenario": {"id": "s2", "municipality_id": pasto,
                                                        "disease_id": trained_ira, "temperature_delta_c": 99}})
        assert "temperature_delta_c" in _receive_until(ws, "simulation.result")["result"]["error"]

        ws.send_json({"type": "dance"})
        assert _receive_until(ws, "error")["code"] == "INVALID_MESSAGE"


def test_live_alert_reaches_the_browser(hub_client, db, trained_ira):
    consaca = db.query(Municipality).filter_by(divipola_code="52207").one().id
    with hub_client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "subscribe", "channel": "alerts", "municipality_id": consaca})
        _receive_until(ws, "alerts.snapshot")
        a = Alert(municipality_id=consaca, disease_id=trained_ira, year=2018, epi_week=5, risk_level="RED",
                  origin="OBSERVED", message="Prueba en vivo", active=True)
        db.add(a)
        db.commit()
        try:
            event = _receive_until(ws, "alert", limit=200)["event"]
            assert event["kind"] == "CREATED" and event["alert"]["id"] == a.id and event["alert"]["level"] == "RED"
        finally:
            db.delete(a)
            db.commit()


def test_internal_events_need_the_token_and_reach_every_socket(hub_client):
    with hub_client.websocket_connect("/ws") as ws:
        ws.receive_json()  # welcome
        body = {"event": "data.updated", "at": "2026-11-10T10:00:00Z", "detail": {"ok": True}}
        assert hub_client.post("/internal/events", json=body).status_code == 401
        r = hub_client.post("/internal/events", json=body, headers={"X-Internal-Token": settings.INTERNAL_TOKEN})
        assert r.status_code == 202 and r.json()["delivered"] >= 1
        assert _receive_until(ws, "system") == {"type": "system", "event": "data.updated",
                                                "at": "2026-11-10T10:00:00Z", "detail": {"ok": True}}


def test_foreign_origin_is_refused(hub_client):
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect) as exc, \
            hub_client.websocket_connect("/ws", headers={"origin": "https://evil.example"}) as ws:
        ws.receive_json()
    assert exc.value.code == realtime.CLOSE_POLICY_VIOLATION


def test_heartbeat_task_is_cancellable():
    async def run():
        task = asyncio.create_task(realtime._heartbeat())
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(run())


def test_service_import_graphs_stay_light():
    """The hub must not load the database or data-science stack, and the gateway not the ML one."""
    import subprocess
    import sys

    code = ("import sys, importlib; importlib.import_module(sys.argv[1]); "
            "print(','.join(m for m in ('pandas', 'sklearn', 'sqlalchemy', 'reportlab') if m in sys.modules))")
    loaded = {service: subprocess.run([sys.executable, "-c", code, service], capture_output=True, text=True,
                                      check=True).stdout.strip()
              for service in ("volcano.realtime.app", "volcano.gateway.app")}
    assert loaded["volcano.realtime.app"] == ""
    assert "sklearn" not in loaded["volcano.gateway.app"] and "pandas" not in loaded["volcano.gateway.app"]
