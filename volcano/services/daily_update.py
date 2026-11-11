"""Daily data update (GitHub Actions triggers it with a cron job, through the gateway).

Each step is isolated: when an external source fails, the error is recorded and the next steps
still run (a Google Trends outage must not stop the weather or the alerts from updating).

    1. Weather: last 14 observed days + 16-day forecast (Open-Meteo).
    2. Searches: Google Trends (honours the database cache; CSV fallback).
    3. Official cases: SIVIGILA on datos.gov.co (Mondays only or on demand; the dataset is published
       months late and is heavy to download).
    4. Model (engine, over gRPC): on Mondays (or when there is no usable model) retrain in the
       background; the other days only regenerate predictions and re-evaluate alerts.
    5. Frontend: on-demand revalidation of the ISR pages (municipality dashboards).
    6. Realtime: tell the open browsers that there is new data.
"""
import logging
import time
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Literal

from sqlalchemy import func, select

from volcano.models import TrainedModel
from volcano.notifications.frontend import revalidate_frontend
from volcano.notifications.realtime import publish_event
from volcano.rpc.client import EngineSyncClient
from volcano.services.search_trends import SearchTrendService
from volcano.services.sivigila import SivigilaService
from volcano.services.weather import WeatherService
from volcano.shared.errors import ConflictError

logger = logging.getLogger("volcano.cron")

Mode = Literal["auto", "yes", "no"]


def _step(name: str, fn: Callable[[], object]) -> dict:
    t0 = time.perf_counter()
    try:
        result = fn()
        if hasattr(result, "model_dump"):
            result = result.model_dump(mode="json")
        return {"step": name, "ok": True, "seconds": round(time.perf_counter() - t0, 1), "result": result}
    except Exception as exc:
        logger.exception("Step %s failed", name)
        return {"step": name, "ok": False, "seconds": round(time.perf_counter() - t0, 1), "error": str(exc)}


class DailyUpdateService:
    def __init__(self, db, engine: EngineSyncClient | None = None, today: date | None = None):
        self.db = db
        self.engine = engine or EngineSyncClient()
        self.today = today or date.today()

    def _is_due(self, mode: Mode) -> bool:
        return mode == "yes" or (mode == "auto" and self.today.weekday() == 0)  # Monday

    def _start_training(self) -> dict:
        try:
            status = self.engine.start_training()
        except ConflictError:
            return {"message": "Ya había un entrenamiento en curso"}  # not an error
        return {"message": "Reentrenamiento iniciado en el motor; al terminar se evalúan las alertas",
                "started_at": status.started_at.isoformat() if status.started_at else None}

    def run(self, sivigila: Mode = "auto", retrain: Mode = "auto") -> dict:
        started = datetime.now(UTC)
        steps = [
            _step("weather", lambda: WeatherService(self.db).sync(past_days=14)),
            _step("trends", lambda: SearchTrendService(self.db).sync()),
        ]
        if self._is_due(sivigila):
            steps.append(_step("sivigila", lambda: SivigilaService(self.db).sync()))

        no_models = (self.db.scalar(select(func.count()).select_from(TrainedModel)) or 0) == 0
        if self._is_due(retrain) or (retrain != "no" and no_models):
            # The engine evaluates alerts, revalidates the frontend and notifies the hub when it finishes
            steps.append(_step("retrain", self._start_training))
        else:
            steps.append(_step("forecasts_and_alerts", lambda: self.engine.refresh_forecasts(evaluate_alerts=True)))
            steps.append(_step("frontend", revalidate_frontend))
        ok = all(s["ok"] for s in steps)
        publish_event("data.updated", {"ok": ok})
        return {"started_at": started.isoformat(), "finished_at": datetime.now(UTC).isoformat(), "ok": ok,
                "steps": steps}
