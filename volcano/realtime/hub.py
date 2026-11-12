"""Connection hub: who is connected, what each client listens to, and fan-out.

Every client gets a bounded outbound queue drained by its own sender task. Broadcasting only puts a
message in each queue (never awaits a socket), so one slow browser cannot stall the others; a client
whose queue fills up is disconnected with code 1013 ("try again later") and its browser reconnects.
"""
import asyncio
import contextlib
import itertools
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from volcano.realtime.protocol import message

logger = logging.getLogger("volcano.realtime.hub")

OUTBOUND_QUEUE_SIZE = 256
CLOSE_TRY_AGAIN_LATER = 1013
_ids = itertools.count(1)


@dataclass(eq=False)
class Client:
    websocket: WebSocket
    id: str = field(default_factory=lambda: f"c{next(_ids)}")
    alerts: bool = False                   # subscribed to the alert feed
    alerts_municipality_id: int | None = None
    awaiting_snapshot: bool = False        # subscribed while the relay was not in sync yet
    outbox: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=OUTBOUND_QUEUE_SIZE))
    closing: bool = False

    def wants_alert(self, alert: dict[str, Any]) -> bool:
        return self.alerts and (self.alerts_municipality_id is None
                                or alert.get("municipality_id") == self.alerts_municipality_id)

    def send(self, payload: dict[str, Any]) -> bool:
        """Queue a message without waiting. False when the client is too slow and must be dropped."""
        if self.closing:
            return False
        try:
            self.outbox.put_nowait(payload)
            return True
        except asyncio.QueueFull:
            return False


class ConnectionHub:
    def __init__(self, max_connections: int = 200):
        self.max_connections = max_connections
        self._clients: set[Client] = set()

    def __len__(self) -> int:
        return len(self._clients)

    @property
    def full(self) -> bool:
        return len(self._clients) >= self.max_connections

    def add(self, client: Client) -> None:
        self._clients.add(client)
        self._announce_presence()

    def remove(self, client: Client) -> None:
        if client in self._clients:
            self._clients.discard(client)
            self._announce_presence()

    def _announce_presence(self) -> None:
        self.broadcast(message("presence", online=len(self._clients)))

    def matching(self, to: Callable[[Client], bool]) -> list[Client]:
        return [c for c in self._clients if to(c)]

    def broadcast(self, payload: dict[str, Any], to: Callable[[Client], bool] = lambda _: True) -> int:
        """Queue `payload` for every matching client; returns how many got it."""
        delivered = 0
        for client in list(self._clients):
            if not to(client):
                continue
            if client.send(payload):
                delivered += 1
            else:
                logger.warning("Client %s is too slow; disconnecting it", client.id)
                self.drop(client)
        return delivered

    def drop(self, client: Client) -> None:
        client.closing = True
        self._clients.discard(client)
        with contextlib.suppress(asyncio.QueueFull):
            client.outbox.put_nowait(None)  # wakes the sender, which closes the socket

    @staticmethod
    async def pump(client: Client) -> None:
        """Sender task: write the client's queue to its socket until a None sentinel or an error."""
        try:
            while (payload := await client.outbox.get()) is not None:
                await client.websocket.send_json(payload)
        except Exception as exc:  # the socket closed under us: nothing else to do
            logger.debug("Sender of %s stopped: %s", client.id, exc)
        finally:
            if client.closing and client.websocket.application_state == WebSocketState.CONNECTED:
                with contextlib.suppress(Exception):
                    await client.websocket.close(code=CLOSE_TRY_AGAIN_LATER)
