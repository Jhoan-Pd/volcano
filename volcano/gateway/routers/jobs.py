"""Scheduled jobs. GitHub Actions calls this endpoint once a day."""
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from volcano.db.session import get_db
from volcano.gateway.deps import verify_cron_secret
from volcano.services.daily_update import DailyUpdateService

router = APIRouter(prefix="/jobs", tags=["Scheduled jobs"], dependencies=[Depends(verify_cron_secret)])


@router.post("/daily-update", summary="Daily update of sources, predictions and alerts (X-Cron-Secret header)")
def daily_update(
    sivigila: Literal["auto", "yes", "no"] = Query("auto", description="auto = Mondays only"),
    retrain: Literal["auto", "yes", "no"] = Query("auto", description="auto = Mondays or when there is no model"),
    db: Session = Depends(get_db),
):
    """Weather → searches → (SIVIGILA) → predictions or retraining (engine) → alerts → frontend.
    Each step reports whether it finished well; a failed one does not stop the rest."""
    return DailyUpdateService(db).run(sivigila=sivigila, retrain=retrain)
