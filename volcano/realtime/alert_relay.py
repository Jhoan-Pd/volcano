"""One upstream gRPC stream of alerts, fanned out to every WebSocket — and only while someone listens.

Without the hub each open browser tab would hold its own `WatchAlerts` stream — and its own engine
thread. The relay keeps exactly one, mirrors the set of active alerts in memory and pushes every
change to the subscribed clients.

The upstream is demand-driven. It opens when the first browser subscribes and closes a short grace
period after the last one leaves. While nobody is watching, the engine does not poll the database at
all, which is what lets a serverless PostgreSQL (Neon) scale to zero instead of being kept awake
around the clock by an idle service.

When the engine restarts or the stream breaks, the relay reconnects with exponential back-off plus
jitter and tells the browsers the feed is "reconnecting". On every (re)connection the engine replays
the active alerts and sends a SYNCED marker. Clients that already hold a snapshot then get the
differences (so nobody misses an alert raised while the stream was down); clients still waiting for
their first snapshot get it whole.
"""
import asyncio
import contextlib
import logging
import random
from typing import Any

from volcano.realtime.hub import Client, ConnectionHub
from volcano.realtime.protocol import message
from volcano.rpc.client import EngineClient

logger = logging.getLogger("volcano.realtime.alerts")

BACKOFF_START_S = 1.0
BACKOFF_MAX_S = 30.0
# How long the upstream outlives its last subscriber: a page reload must not tear it down
IDLE_GRACE_S = 60.0
Alert = dict[str, Any]


class AlertRelay:
    def __init__(self, hub: ConnectionHub, engine: EngineClient, idle_grace_s: float = IDLE_GRACE_S):
        self.hub = hub
        self.engine = engine
        self.idle_grace_s = idle_grace_s
        self.active: dict[int, Alert] = {}
        self.connected = False
        self._synced_once = False  # since the upstream was last opened
        self._replay: dict[int, Alert] | None = None
        self._task: asyncio.Task | None = None
        self._idle_timer: asyncio.TimerHandle | None = None

    # ── state ────────────────────────────────────────────────────────────────
    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def status(self) -> str:
        """idle (nobody listening) · connecting (first sync pending) · connected · reconnecting."""
        if self.connected:
            return "connected"
        if not self.running:
            return "idle"
        return "reconnecting" if self._synced_once else "connecting"

    def snapshot(self, municipality_id: int | None = None) -> list[Alert]:
        return [a for a in self.active.values() if municipality_id is None or a["municipality_id"] == municipality_id]

    # ── demand ───────────────────────────────────────────────────────────────
    def subscribe(self, client: Client, municipality_id: int | None) -> None:
        client.alerts, client.alerts_municipality_id = True, municipality_id
        self.demand_changed()
        if self.connected:
            self._send_snapshot(client)
        else:  # the snapshot follows as soon as the engine finishes its replay
            client.awaiting_snapshot = True
            client.send(message("upstream", status=self.status))

    def unsubscribe(self, client: Client) -> None:
        client.alerts = client.awaiting_snapshot = False
        self.demand_changed()

    def demand_changed(self) -> None:
        """Open the upstream when someone listens; schedule its close when nobody does.
        Call it after a client subscribes, unsubscribes or disconnects."""
        if self.hub.matching(lambda c: c.alerts):
            if self._idle_timer is not None:
                self._idle_timer.cancel()
                self._idle_timer = None
            self.start()
        elif self.running and self._idle_timer is None:
            self._idle_timer = asyncio.get_running_loop().call_later(self.idle_grace_s, self._go_idle)

    def _go_idle(self) -> None:
        self._idle_timer = None
        if self.hub.matching(lambda c: c.alerts) or not self.running:
            return
        logger.info("No alert subscribers left: closing the upstream stream")
        self._task.cancel()
        self._reset()

    def _reset(self) -> None:
        self._task = None
        self.active, self._replay = {}, None
        self.connected = self._synced_once = False

    def start(self) -> None:
        if not self.running:
            self._task = asyncio.create_task(self._run(), name="alert-relay")

    async def stop(self) -> None:
        if self._idle_timer is not None:
            self._idle_timer.cancel()
            self._idle_timer = None
        task = self._task
        self._reset()
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    # ── event handling (pure, unit-tested) ───────────────────────────────────
    def _send_snapshot(self, client: Client) -> None:
        client.awaiting_snapshot = False
        client.send(message("alerts.snapshot", alerts=self.snapshot(client.alerts_municipality_id),
                            upstream="connected"))

    def _publish(self, kind: str, at: str, alert: Alert) -> None:
        """Send a change to the clients that already hold a snapshot to apply it to."""
        event = {"kind": kind, "at": at, "alert": alert}
        self.hub.broadcast(message("alert", event=event),
                           to=lambda c: c.wants_alert(alert) and not c.awaiting_snapshot)

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
        self._synced_once = True
        self._set_connected(True)
        for client in self.hub.matching(lambda c: c.alerts and c.awaiting_snapshot):
            self._send_snapshot(client)

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
