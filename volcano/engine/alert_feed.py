"""Broadcast alert changes to every open stream (publish/subscribe).

Alerts can change from two processes: the gateway (daily job, «Evaluar alertas» button) and the
engine itself (after training). So the engine does not wait to be told: a single thread compares
the active alerts with the previous snapshot every `interval_s` and publishes the differences
(created, updated, closed) to each subscriber's queue.

One thread for every client, not one per client: thirty subscribers cost one query every 10 s, not
thirty. In practice there is a single subscriber — the realtime hub, which fans the events out to
all its WebSockets — but the feed does not depend on that. The thread only polls while someone is
subscribed.
"""
import logging
import queue
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select

from volcano.models import Alert
from volcano.rpc import engine_pb2 as pb
from volcano.rpc.conversion import level_to_pb
from volcano.shared.epi import label

logger = logging.getLogger("volcano.engine.alerts")
Kind = pb.AlertEvent.Kind


@dataclass(frozen=True)
class AlertSnapshot:
    """What the browser needs from an alert; immutable so snapshots compare with ==."""
    id: int
    municipality_id: int
    municipality: str
    disease_id: int
    disease: str
    week: str
    level: str
    origin: str
    message: str

    def to_pb(self) -> pb.Alert:
        return pb.Alert(id=self.id, municipality_id=self.municipality_id, municipality=self.municipality,
                        disease_id=self.disease_id, disease=self.disease, week=self.week,
                        level=level_to_pb(self.level), origin=self.origin, message=self.message)


@dataclass(eq=False)
class Subscription:
    municipality_id: int | None = None
    events: queue.Queue = field(default_factory=lambda: queue.Queue(maxsize=500))

    def accepts(self, snapshot: AlertSnapshot) -> bool:
        return self.municipality_id is None or snapshot.municipality_id == self.municipality_id


def event(kind: int, snapshot: AlertSnapshot) -> pb.AlertEvent:
    return pb.AlertEvent(kind=kind, alert=snapshot.to_pb(), at=datetime.now(UTC).isoformat())


class AlertFeed:
    def __init__(self, sessions, interval_s: float = 10.0):
        self._sessions = sessions
        self.interval_s = interval_s
        self._snapshot: dict[int, AlertSnapshot] | None = None
        self._subscribers: set[Subscription] = set()
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ── reading ──────────────────────────────────────────────────────────────
    def _read(self) -> dict[int, AlertSnapshot]:
        with self._sessions() as db:
            return {a.id: AlertSnapshot(a.id, a.municipality_id, a.municipality.name, a.disease_id, a.disease.name,
                                        label(a.year, a.epi_week), a.risk_level, a.origin, a.message)
                    for a in db.scalars(select(Alert).where(Alert.active.is_(True)))}

    @staticmethod
    def differences(before: dict[int, AlertSnapshot], now: dict[int, AlertSnapshot]) -> list[tuple[int, AlertSnapshot]]:
        changes = [(Kind.KIND_CREATED if i not in before else Kind.KIND_UPDATED, s)
                   for i, s in now.items() if before.get(i) != s]
        changes += [(Kind.KIND_CLOSED, s) for i, s in before.items() if i not in now]
        return changes

    # ── subscriptions ────────────────────────────────────────────────────────
    def subscribe(self, municipality_id: int | None = None) -> tuple[Subscription, list[pb.AlertEvent]]:
        """Register the subscriber and return the alerts that are active right now."""
        sub = Subscription(municipality_id)
        with self._lock:
            # Nobody was listening, so nothing kept the snapshot current: read it again
            if self._snapshot is None or not self._subscribers:
                self._snapshot = self._read()
            initial = [event(Kind.KIND_ACTIVE, s) for s in self._snapshot.values() if sub.accepts(s)]
            self._subscribers.add(sub)
            self._ensure_thread()
        return sub, initial

    def unsubscribe(self, sub: Subscription) -> None:
        with self._lock:
            self._subscribers.discard(sub)

    @property
    def subscribers(self) -> int:
        return len(self._subscribers)

    # ── publishing ───────────────────────────────────────────────────────────
    def check(self) -> int:
        """Compare with the previous snapshot and publish the changes. Returns how many there were."""
        now = self._read()
        with self._lock:
            changes = self.differences(self._snapshot or {}, now) if self._snapshot is not None else []
            self._snapshot = now
            for kind, snapshot in changes:
                for sub in self._subscribers:
                    if sub.accepts(snapshot):
                        try:
                            sub.events.put_nowait(event(kind, snapshot))
                        except queue.Full:  # a client that does not read does not slow the others down
                            logger.warning("Subscriber saturated; an event was dropped")
        return len(changes)

    def check_soon(self) -> None:
        """Ask for an immediate check (e.g. after training) without waiting for the interval."""
        self._wake.set()

    def _ensure_thread(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._loop, daemon=True, name="alert-feed")
            self._thread.start()

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._wake.wait(self.interval_s)
            self._wake.clear()
            if self._stop.is_set():
                break
            if self._subscribers:
                try:
                    self.check()
                except Exception:
                    logger.exception("Could not check the alerts")

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
