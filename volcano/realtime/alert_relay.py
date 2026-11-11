"""One upstream gRPC stream of alerts, fanned out to every WebSocket.

Without the hub each open browser tab would hold its own `WatchAlerts` stream — and its own engine
thread. The relay keeps exactly one, mirrors the set of active alerts in memory and pushes every
change to the subscribed clients. A client that subscribes later gets the current snapshot at once,
without touching the engine.

When the engine restarts or the stream breaks, the relay reconnects with exponential back-off plus
jitter and tells the browsers the feed is "reconnecting". On reconnection the engine replays the
active alerts and sends a SYNCED marker; the relay then diffs that replay against what it had and
announces whatever changed while it was disconnected, so no browser misses an alert.
"""
import asyncio
import contextlib
import logging
import random
from typing import Any

from volcano.realtime.hub import ConnectionHub
from volcano.realtime.protocol import message
from volcano.rpc.client import EngineClient

logger = logging.getLogger("volcano.realtime.alerts")

BACKOFF_START_S = 1.0
BACKOFF_MAX_S = 30.0
Alert = dict[str, Any]


class AlertRelay:
    def __init__(self, hub: ConnectionHub, engine: EngineClient):
        self.hub = hub
        self.engine = engine
        self.active: dict[int, Alert] = {}
        self.connected = False
        self._replay: dict[int, Alert] | None = None
        self._task: asyncio.Task | None = None

    @property
    def status(self) -> str:
        return "connected" if self.connected else "reconnecting"

    def snapshot(self, municipality_id: int | None = None) -> list[Alert]:
        return [a for a in self.active.values() if municipality_id is None or a["municipality_id"] == municipality_id]

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="alert-relay")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    # ── event handling (pure, unit-tested) ───────────────────────────────────
    def _publish(self, kind: str, at: str, alert: Alert) -> None:
        event = {"kind": kind, "at": at, "alert": alert}
        self.hub.broadcast(message("alert", event=event), to=lambda c: c.wants_alert(alert))

    def handle(self, event: dict[str, Any]) -> None:
        kind, at, alert = event["kind"], event["at"], event["alert"]
        if kind == "ACTIVE":  # part of the replay that follows every (re)connection
            self._replay = self._replay if self._replay is not None else {}
            self._replay[alert["id"]] = alert
        elif kind == "SYNCED":
            self._finish_replay(at)
        elif kind == "CLOSED":
            self.active.pop(alert["id"], None)
            self._publish(kind, at, alert)
        else:  # CREATED | UPDATED
            self.active[alert["id"]] = alert
            self._publish(kind, at, alert)

    def _finish_replay(self, at: str) -> None:
        replay, self._replay = self._replay or {}, None
        for alert_id, alert in self.active.items():
            if alert_id not in replay:
                self._publish("CLOSED", at, alert)
        for alert_id, alert in replay.items():
            if alert_id not in self.active:
                self._publish("CREATED", at, alert)
            elif self.active[alert_id] != alert:
                self._publish("UPDATED", at, alert)
        self.active = replay
        self._set_connected(True)

    def _set_connected(self, value: bool) -> None:
        if value != self.connected:
            self.connected = value
            self.hub.broadcast(message("upstream", status=self.status), to=lambda c: c.alerts)

    # ── upstream loop ────────────────────────────────────────────────────────
    async def _run(self) -> None:
        delay = BACKOFF_START_S
        while True:
            try:
                async for event in self.engine.watch_alerts():
                    self.handle(event.model_dump())
                    if self.connected:
                        delay = BACKOFF_START_S
                logger.info("Alert stream ended by the engine")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Alert stream lost (%s); retrying in about %.0f s", exc, delay)
            self._replay = None
            self._set_connected(False)
            await asyncio.sleep(delay * random.uniform(0.8, 1.2))  # noqa: S311 - jitter, not cryptography
            delay = min(delay * 2, BACKOFF_MAX_S)
