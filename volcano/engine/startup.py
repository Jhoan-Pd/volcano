"""Start-up check of the engine: make sure every active disease has a usable model.

A model may be missing (first deploy: the seed loaded cases but nothing is trained yet) or unusable
(its artifact was written by an older version of the code, e.g. before the features were renamed).
In both cases training starts in a background thread so the gRPC port opens immediately; meanwhile
the dashboard keeps showing the predictions already stored in the database.
"""
import logging
from collections.abc import Callable

from sqlalchemy import func, select

from volcano.db.session import SessionLocal
from volcano.models import OfficialCase
from volcano.services.forecasting import ForecastingService
from volcano.services.training import start_in_thread
from volcano.shared.errors import ConflictError

logger = logging.getLogger("volcano.engine.startup")


def train_if_needed(sessions=SessionLocal, on_done: Callable[[], None] | None = None) -> bool:
    """Returns True when a training run was started."""
    try:
        with sessions() as db:
            has_cases = (db.scalar(select(func.count()).select_from(OfficialCase)) or 0) > 0
            pending = ForecastingService(db).diseases_needing_training() if has_cases else []
        if not pending:
            return False
        logger.info("Training on start-up (%s)", ", ".join(d.code for d in pending))
        start_in_thread(name="startup-training", on_done=on_done)
        return True
    except ConflictError:
        return False
    except Exception as exc:  # the engine must start even if this check fails
        logger.warning("Could not check the models on start-up: %s", exc)
        return False
