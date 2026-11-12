"""Wire protocol of the realtime hub: JSON messages over a single WebSocket (`/ws`).

Every message is an object with a `type`. One socket multiplexes every live feature, so a page opens
one connection no matter how many widgets need live data.

Client → server
    {"type": "subscribe",   "channel": "alerts", "municipality_id": 1 | null}
    {"type": "unsubscribe", "channel": "alerts"}
    {"type": "simulate",    "scenario": {id, municipality_id, disease_id, rain_change_pct, …}}
    {"type": "ping"}

Server → client
    {"type": "welcome", "client_id", "protocol", "heartbeat_s", "server_time"}
    {"type": "alerts.snapshot", "alerts": [...], "upstream": "connected"}
    {"type": "alert", "event": {"kind": "CREATED" | "UPDATED" | "CLOSED", "at", "alert": {...}}}
    {"type": "simulation.result", "result": {...}}
    {"type": "presence", "online": 3}
    {"type": "system", "event": "data.updated" | "model.trained" | …, "at", "detail"}
    {"type": "upstream", "status": "connecting" | "connected" | "reconnecting"}
    {"type": "ping"} · {"type": "pong"}
    {"type": "error", "code", "message"}

A subscriber always ends up with exactly one `alerts.snapshot`: at once when the hub is in sync with
the engine, otherwise right after it (an `upstream` message says which case it is meanwhile).
"""
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, TypeAdapter

from volcano.schemas.engine import ScenarioIn

PROTOCOL_VERSION = 1
Channel = Literal["alerts"]


class Subscribe(BaseModel):
    type: Literal["subscribe"]
    channel: Channel
    municipality_id: int | None = None


class Unsubscribe(BaseModel):
    type: Literal["unsubscribe"]
    channel: Channel


class Simulate(BaseModel):
    type: Literal["simulate"]
    scenario: ScenarioIn


class Ping(BaseModel):
    type: Literal["ping"]


ClientMessage = Annotated[Subscribe | Unsubscribe | Simulate | Ping, Field(discriminator="type")]
client_message = TypeAdapter(ClientMessage)


class SystemEventIn(BaseModel):
    """Body of `POST /internal/events` (gateway or engine → hub)."""
    event: Literal["data.updated", "model.trained", "alerts.evaluated"]
    at: str
    detail: dict[str, Any] = {}


def message(kind: str, **fields: Any) -> dict[str, Any]:
    return {"type": kind, **fields}


def error(code: str, text: str) -> dict[str, Any]:
    """`text` is Spanish: the frontend may show it to the user as is."""
    return message("error", code=code, message=text)
