"""Background retraining and its status (runs inside the engine).

On Render's free plan (0.1 CPU) training the 4 models takes minutes, so callers never wait:
the engine runs it in a thread and the gateway shows progress over SSE or polls the status.

`TrainingControl` wraps the state shared between threads (a lock protects every change) behind a
small interface: start, finish and read. `retrain()` orchestrates training → predictions → alerts →
notifications.
"""
import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime

from volcano.db.session import SessionLocal
from volcano.ml.progress import Progress, ProgressEvent, Stage, no_progress, scaled
from volcano.notifications.frontend import revalidate_frontend
from volcano.notifications.realtime import publish_event
from volcano.schemas.model import TrainingStatus
from volcano.services.alerts import AlertService
from volcano.services.forecasting import ForecastingService
from volcano.shared.errors import ConflictError

logger = logging.getLogger("volcano.training")


class TrainingControl:
    """Status of the latest retraining; guarantees two never run at the same time."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._status = TrainingStatus(running=False)

    def status(self) -> TrainingStatus:
        with self._lock:
            return self._status.model_copy()

    def start(self) -> TrainingStatus:
        with self._lock:
            if self._status.running:
                raise ConflictError("Ya hay un entrenamiento en curso. Espera a que termine.")
            self._status = TrainingStatus(running=True, started_at=datetime.now(UTC), message="Entrenando…")
            return self._status.model_copy()

    def finish(self, message: str, errors: list[str] | None = None) -> None:
        with self._lock:
            self._status = TrainingStatus(running=False, started_at=self._status.started_at,
                                          finished_at=datetime.now(UTC), message=message, errors=errors or [])

    def reset(self) -> None:
        """Back to the initial state (handy in tests)."""
        with self._lock:
            self._status = TrainingStatus(running=False)


control = TrainingControl()


def retrain(disease_id: int | None = None, progress: Progress = no_progress,
            on_done: Callable[[], None] | None = None) -> None:
    """Train, regenerate predictions and re-evaluate alerts. Meant for a background thread: it never
    raises; the result (or the error) ends up in `control.status()` and, when `progress` is given,
    every step is reported too (the engine streams it live)."""
    progress(ProgressEvent(Stage.STARTED, "Entrenamiento iniciado", 0.0))
    try:
        with SessionLocal() as db:
            models, errors = ForecastingService(db).train(disease_id, scaled(progress, 0.0, 0.95))
            progress(ProgressEvent(Stage.ALERTS, "Recalculando alertas tempranas", 0.95))
            alerts = AlertService(db).evaluate()
        revalidate_frontend()  # the frontend's ISR dashboards regenerate with the new predictions
        message = (f"{len(models)} modelo(s) entrenado(s) y predicciones actualizadas; "
                   f"{alerts.active} alerta(s) activa(s), {alerts.new} nueva(s)")
        control.finish(message, errors)
        publish_event("model.trained", {"models": len(models), "alerts_active": alerts.active})
        progress(ProgressEvent(Stage.FINISHED, message, 1.0))
    except Exception as exc:
        logger.exception("Retraining failed")
        control.finish("El entrenamiento falló", [str(exc)])
        progress(ProgressEvent(Stage.FAILED, f"El entrenamiento falló: {exc}", 1.0))
    finally:
        if on_done is not None:
            on_done()


def start_in_thread(disease_id: int | None = None, name: str = "retraining",
                    on_done: Callable[[], None] | None = None) -> TrainingStatus:
    """Mark the start (409 when one is already running) and train in a separate thread."""
    status = control.start()
    threading.Thread(target=retrain, kwargs={"disease_id": disease_id, "on_done": on_done},
                     daemon=True, name=name).start()
    return status
