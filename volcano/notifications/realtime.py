"""Publish system events to the realtime hub, which fans them out to every open WebSocket.

The gateway and the engine call this after the data changes (daily update, retraining, alert
evaluation) so open dashboards can refresh themselves instead of waiting for the next visit.

It is fire-and-forget over loopback HTTP: if the hub is down the event is simply lost (it is a
"refresh hint", never the source of truth) and the caller is not slowed down.
"""
import logging
from datetime import UTC, datetime
from typing import Any, Literal

import httpx

from volcano.shared.config import settings

logger = logging.getLogger("volcano.realtime.publisher")

SystemEvent = Literal["data.updated", "model.trained", "alerts.evaluated"]
INTERNAL_HEADER = "X-Internal-Token"


def publish_event(event: SystemEvent, detail: dict[str, Any] | None = None, timeout_s: float = 2.0) -> bool:
    payload = {"event": event, "at": datetime.now(UTC).isoformat(), "detail": detail or {}}
    try:
        r = httpx.post(f"{settings.REALTIME_INTERNAL_URL.rstrip('/')}/internal/events", json=payload,
                       headers={INTERNAL_HEADER: settings.INTERNAL_TOKEN}, timeout=timeout_s)
        r.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        logger.info("Realtime hub unreachable, event %s dropped: %s", event, exc)
        return False
