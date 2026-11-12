"""Realtime microservice: the WebSocket hub.

    Local:  uvicorn volcano.realtime.app:app --port 8002

Endpoints (the edge proxy routes `/ws` and `/realtime/*` here):
    WS   /ws                  multiplexed socket: live alerts, scenario simulator, presence, system events
    GET  /realtime/health     liveness + connections + upstream status (touches nothing else)
    POST /internal/events     gateway/engine → hub (shared token; only reachable on loopback)

The hub never touches the database: alerts come from the engine's `WatchAlerts` stream (one upstream
for every browser, open only while someone is subscribed) and simulations from `SimulateScenarios`.
Its import graph is deliberately small (no pandas, no scikit-learn) so the process costs a few tens
of MB in the shared container. As the one service that is pure asyncio it also hosts the keep-awake
loop of free-plan deployments (see keep_awake.py).
"""
import asyncio
import contextlib
import logging
import re
import secrets
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, Header, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from volcano import __version__
from volcano.notifications.realtime import INTERNAL_HEADER
from volcano.realtime.alert_relay import AlertRelay
from volcano.realtime.hub import Client, ConnectionHub
from volcano.realtime.keep_awake import keep_awake, parse_hours
from volcano.realtime.protocol import (
    PROTOCOL_VERSION,
    Ping,
    Simulate,
    Subscribe,
    SystemEventIn,
    Unsubscribe,
    client_message,
    error,
    message,
)
from volcano.realtime.simulation import SimulationSession
from volcano.rpc.client import EngineClient, engine_client
from volcano.shared.config import settings
from volcano.shared.log_config import configure_logging

logger = logging.getLogger("volcano.realtime")

CLOSE_POLICY_VIOLATION = 1008
CLOSE_TRY_AGAIN_LATER = 1013
MAX_MESSAGE_BYTES = 8 * 1024

hub = ConnectionHub(max_connections=settings.REALTIME_MAX_CONNECTIONS)


def engine() -> EngineClient:
    """The engine client (tests point it at their own gRPC server)."""
    return engine_client()


class _State:
    relay: AlertRelay


state = _State()


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging("realtime")
    state.relay = AlertRelay(hub, engine())  # its upstream opens with the first subscriber
    tasks = [asyncio.create_task(_heartbeat(), name="heartbeat")]
    if settings.KEEP_AWAKE and settings.KEEP_AWAKE_URL:
        tasks.append(asyncio.create_task(
            keep_awake(settings.KEEP_AWAKE_URL, settings.KEEP_AWAKE_INTERVAL_S,
                       parse_hours(settings.KEEP_AWAKE_HOURS), settings.LOCAL_UTC_OFFSET_HOURS),
            name="keep-awake"))
    yield
    for task in tasks:
        task.cancel()
    await state.relay.stop()
    await engine().close()


app = FastAPI(title="Realtime hub", version=__version__, lifespan=lifespan, docs_url=None, redoc_url=None)


async def _heartbeat() -> None:
    """Application-level ping: keeps idle sockets alive through proxies (Render closes silent ones)
    and lets the browser detect a dead connection faster than TCP would."""
    while True:
        await asyncio.sleep(settings.REALTIME_HEARTBEAT_S)
        hub.broadcast(message("ping"))


def origin_allowed(origin: str | None) -> bool:
    """Browsers do not apply CORS to WebSockets, so the hub checks the Origin itself (prevents
    cross-site WebSocket hijacking). Clients without an Origin header (scripts, tests) are allowed."""
    if not origin:
        return True
    origin = origin.rstrip("/")
    if origin in settings.cors_origins:
        return True
    return bool(settings.CORS_ORIGIN_REGEX and re.fullmatch(settings.CORS_ORIGIN_REGEX, origin))


@app.get("/realtime/health")
def health():
    return {"status": "ok", "connections": len(hub), "alerts_upstream": state.relay.status,
            "active_alerts": len(state.relay.active)}


@app.post("/internal/events", status_code=status.HTTP_202_ACCEPTED)
def internal_event(event: SystemEventIn, x_internal_token: str = Header(default="", alias=INTERNAL_HEADER)):
    if not secrets.compare_digest(x_internal_token, settings.INTERNAL_TOKEN):
        return JSONResponse(status_code=401, content={"error": {"code": "NOT_AUTHENTICATED",
                                                                "message": "Invalid internal token"}})
    delivered = hub.broadcast(message("system", event=event.event, at=event.at, detail=event.detail))
    return {"delivered": delivered}


async def _handle(client: Client, simulation: SimulationSession, raw: str) -> None:
    if len(raw) > MAX_MESSAGE_BYTES:
        client.send(error("MESSAGE_TOO_LARGE", "El mensaje es demasiado grande"))
        return
    try:
        msg = client_message.validate_json(raw)
    except ValidationError as exc:
        first = exc.errors()[0]
        client.send(error("INVALID_MESSAGE", f"Mensaje inválido: {first['msg']}"))
        return
    match msg:
        case Subscribe(municipality_id=municipality_id):
            state.relay.subscribe(client, municipality_id)
        case Unsubscribe():
            state.relay.unsubscribe(client)
        case Simulate(scenario=scenario):
            await simulation.submit(scenario)
        case Ping():
            client.send(message("pong"))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    if not origin_allowed(websocket.headers.get("origin")):
        await websocket.close(code=CLOSE_POLICY_VIOLATION)
        return
    if hub.full:
        await websocket.close(code=CLOSE_TRY_AGAIN_LATER)
        return
    await websocket.accept()
    client = Client(websocket)
    simulation = SimulationSession(client, engine())
    sender = asyncio.create_task(hub.pump(client), name=f"sender-{client.id}")
    client.send(message("welcome", client_id=client.id, protocol=PROTOCOL_VERSION,
                        heartbeat_s=settings.REALTIME_HEARTBEAT_S, server_time=datetime.now(UTC).isoformat()))
    hub.add(client)
    try:
        while not client.closing:
            await _handle(client, simulation, await websocket.receive_text())
    except WebSocketDisconnect:
        pass
    finally:
        hub.remove(client)
        state.relay.demand_changed()
        await simulation.close()
        if not client.closing:
            client.closing = True
            with contextlib.suppress(asyncio.QueueFull):
                client.outbox.put_nowait(None)
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await asyncio.wait_for(sender, timeout=2)
