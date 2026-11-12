"""Keeps a free-plan deployment from being put to sleep.

Render spins a free web service down after 15 minutes without INBOUND traffic and takes about a
minute to bring it back, which every first visitor pays for. A scheduler outside the service is the
obvious fix, but GitHub Actions' cron proved far too irregular for it (runs hours apart). So the
service asks for its own public URL at a fixed interval: the request leaves through the internet and
comes back through Render's router as ordinary inbound traffic.

It pings `/live`, which does not touch the database, so staying awake costs no database compute.
What it cannot do is wake a service that is already asleep (nothing is running to send the ping);
the first request after a deploy or a restart does that.

Render grants 750 free instance hours per workspace and month: enough for ONE service awake around
the clock. With more free services in the workspace, narrow KEEP_AWAKE_HOURS or turn it off.
"""
import asyncio
import logging
import random
from datetime import UTC, datetime, timedelta

import httpx

logger = logging.getLogger("volcano.realtime.keep_awake")

PING_TIMEOUT_S = 10.0


def parse_hours(spec: str) -> tuple[int, int]:
    """'6-23' → (6, 23): awake from 06:00 up to, not including, 23:00. '0-24' means always."""
    start, _, end = spec.partition("-")
    hours = int(start), int(end)
    if not (0 <= hours[0] < hours[1] <= 24):
        raise ValueError(f"KEEP_AWAKE_HOURS must look like '6-23' (0 ≤ start < end ≤ 24), got {spec!r}")
    return hours


def within_hours(hours: tuple[int, int], utc_offset_hours: int, now: datetime | None = None) -> bool:
    local = (now or datetime.now(UTC)) + timedelta(hours=utc_offset_hours)
    return hours[0] <= local.hour < hours[1]


async def keep_awake(base_url: str, interval_s: float, hours: tuple[int, int], utc_offset_hours: int,
                     transport: httpx.AsyncBaseTransport | None = None) -> None:
    """Runs until cancelled. `transport` lets tests observe the pings without a network."""
    url = f"{base_url.rstrip('/')}/live"
    logger.info("Keep-awake on: %s every %.0f s, local hours %d-%d", url, interval_s, *hours)
    async with httpx.AsyncClient(timeout=PING_TIMEOUT_S, transport=transport) as client:
        while True:
            await asyncio.sleep(interval_s * random.uniform(0.9, 1.0))  # noqa: S311 - jitter, not cryptography
            if not within_hours(hours, utc_offset_hours):
                continue
            try:
                (await client.get(url)).raise_for_status()
            except httpx.HTTPError as exc:  # one missed ping is harmless; the next one is minutes away
                logger.warning("Keep-awake ping failed: %s", exc)
