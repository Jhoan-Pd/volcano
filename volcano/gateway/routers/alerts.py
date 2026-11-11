"""Early alerts: the active ones are public (banner); managing them is for the ADMIN."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from volcano.db.session import get_db
from volcano.gateway.deps import admin_only
from volcano.schemas.alert import AlertFilters, AlertOut, EvaluationResult
from volcano.schemas.common import Page
from volcano.services.alerts import AlertService

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("/active", response_model=list[AlertOut], summary="Current alerts (high or very high risk)")
def active(db: Session = Depends(get_db)):
    return AlertService(db).active()


@router.get("/search", response_model=Page[AlertOut], summary="Search the alert history (public)")
def search(filters: AlertFilters = Depends(), offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
           db: Session = Depends(get_db)):
    """Aggregated data (the same content as the public alerts CSV). The frontend's search page renders it
    on the server for every request (SSR)."""
    return AlertService(db).search(filters, offset, limit)


@router.get("", response_model=Page[AlertOut], dependencies=[Depends(admin_only)], summary="Alert history — ADMIN only")
def list_alerts(active: bool | None = Query(None), offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=200),
                db: Session = Depends(get_db)):
    return AlertService(db).list_page(active, offset, limit)


@router.post("/evaluate", response_model=EvaluationResult, dependencies=[Depends(admin_only)],
             summary="Re-evaluate alerts now and send pending e-mails — ADMIN only")
def evaluate(send_email: bool = Query(True), db: Session = Depends(get_db)):
    return AlertService(db).evaluate(send_email=send_email)


@router.patch("/{alert_id}/close", response_model=AlertOut, dependencies=[Depends(admin_only)],
              summary="Close an alert (it only reopens if the risk gets worse) — ADMIN only")
def close(alert_id: int, db: Session = Depends(get_db)):
    return AlertService(db).close(alert_id)
