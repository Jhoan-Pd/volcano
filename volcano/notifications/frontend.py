"""Tell the frontend (Next.js on Vercel) that there is new data.

Each municipality's dashboard is a static page with ISR: Vercel serves it from its CDN and
regenerates it at most once an hour. When the cron job or a retraining changes the data there is no
need to wait that hour: `/api/revalidate` (on-demand revalidation) is called and the next visit gets
the new version.

Without REVALIDATE_SECRET nothing happens (local development and tests).
"""
import logging

import httpx

from volcano.shared.config import settings

logger = logging.getLogger("volcano.frontend")


def revalidate_frontend() -> dict:
    if not settings.REVALIDATE_SECRET:
        return {"revalidated": False, "reason": "REVALIDATE_SECRET is not configured"}
    url = f"{settings.FRONTEND_URL.rstrip('/')}/api/revalidate"
    try:
        r = httpx.post(url, headers={"Authorization": f"Bearer {settings.REVALIDATE_SECRET}"}, timeout=15)
        r.raise_for_status()
        return {"revalidated": True, **r.json()}
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Could not revalidate the frontend (%s): %s", url, exc)
        return {"revalidated": False, "reason": str(exc)}
