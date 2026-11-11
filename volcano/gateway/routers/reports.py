"""Downloadable reports (public: they only contain the dashboard's aggregated data).

File names stay Spanish because people save them on their computers.
"""
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from volcano.db.session import get_db
from volcano.models import Municipality

router = APIRouter(prefix="/reports", tags=["Reports"])
CSV = "text/csv; charset=utf-8"


def _service(db: Session):
    # Deferred import: ReportLab is only loaded the first time somebody downloads a report
    from volcano.services.reports import ReportService  # noqa: PLC0415

    return ReportService(db)


def download_name(base: str, ext: str, suffix: str | None = None) -> str:
    clean = "".join(ch if ch.isalnum() else "-" for ch in (suffix or "").lower()).strip("-")
    return f"{base}{'-' + clean if clean else ''}-{date.today():%Y%m%d}.{ext}"


def _download(content: bytes, media_type: str, filename: str) -> Response:
    return Response(content=content, media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/cases.csv", summary="Weekly cases as CSV (optional filters)")
def cases_csv(municipality_id: int | None = None, disease_id: int | None = None,
              since_year: int | None = Query(None, ge=2000, le=2100), db: Session = Depends(get_db)):
    return _download(_service(db).cases_csv(municipality_id, disease_id, since_year), CSV,
                     download_name("casos", "csv"))


@router.get("/predictions.csv", summary="Current predictions for the next 4 weeks as CSV")
def predictions_csv(municipality_id: int | None = None, db: Session = Depends(get_db)):
    return _download(_service(db).predictions_csv(municipality_id), CSV, download_name("predicciones", "csv"))


@router.get("/alerts.csv", summary="Alert history as CSV")
def alerts_csv(active_only: bool = False, db: Session = Depends(get_db)):
    return _download(_service(db).alerts_csv(active_only), CSV, download_name("alertas", "csv"))


@router.get("/summary.pdf", summary="Municipality PDF report: traffic light, prediction, alerts, volcano, models")
def summary_pdf(municipality_id: int, db: Session = Depends(get_db)):
    pdf = _service(db).summary_pdf(municipality_id)
    m = db.get(Municipality, municipality_id)
    return _download(pdf, "application/pdf", download_name("reporte-riesgo", "pdf", m.name if m else None))
