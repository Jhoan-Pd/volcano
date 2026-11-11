"""Pharmacy panel: weekly sales report per category (PHARMACY and ADMIN roles)."""
from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from volcano.db.session import get_db
from volcano.gateway.deps import pharmacy_or_admin
from volcano.models import User
from volcano.schemas.pharmacy import MyPharmacy, PharmacySalesIndex, WeeklyReportIn, WeeklyReportOut, WeeklyReportUpdate
from volcano.services.pharmacy_reports import PharmacyReportService
from volcano.shared.epi import label, last_complete_week, shift, week_start
from volcano.sources.pharmacy import PharmacySource

router = APIRouter(prefix="/pharmacy", tags=["Pharmacies (reports)"])

YearPath = Path(ge=2015, le=2100)
WeekPath = Path(ge=1, le=53)


@router.get("/me", response_model=MyPharmacy, summary="My pharmacy and the weeks I can report")
def my_pharmacy(pharmacy_id: int | None = Query(None, description="ADMIN only"), db: Session = Depends(get_db),
                user: User = Depends(pharmacy_or_admin)):
    return PharmacyReportService(db, user).my_pharmacy(pharmacy_id)


@router.get("/reports", response_model=list[WeeklyReportOut], summary="Report history (newest first)")
def history(pharmacy_id: int | None = Query(None), weeks: int = Query(26, ge=1, le=260),
            db: Session = Depends(get_db), user: User = Depends(pharmacy_or_admin)):
    return PharmacyReportService(db, user).history(pharmacy_id, weeks)


@router.get("/reports/{year}/{week}", response_model=WeeklyReportOut, summary="Report of one week")
def get_report(year: int = YearPath, week: int = WeekPath, pharmacy_id: int | None = Query(None),
               db: Session = Depends(get_db), user: User = Depends(pharmacy_or_admin)):
    return PharmacyReportService(db, user).get(year, week, pharmacy_id)


@router.post("/reports", response_model=WeeklyReportOut, status_code=status.HTTP_201_CREATED,
             summary="File the report of one week")
def create_report(payload: WeeklyReportIn, db: Session = Depends(get_db), user: User = Depends(pharmacy_or_admin)):
    return PharmacyReportService(db, user).create(payload)


@router.put("/reports/{year}/{week}", response_model=WeeklyReportOut, summary="Fix the report of one week")
def update_report(payload: WeeklyReportUpdate, year: int = YearPath, week: int = WeekPath,
                  pharmacy_id: int | None = Query(None), db: Session = Depends(get_db),
                  user: User = Depends(pharmacy_or_admin)):
    return PharmacyReportService(db, user).update(year, week, payload.items, pharmacy_id)


@router.delete("/reports/{year}/{week}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete one week's report")
def delete_report(year: int = YearPath, week: int = WeekPath, pharmacy_id: int | None = Query(None),
                  db: Session = Depends(get_db), user: User = Depends(pharmacy_or_admin)):
    PharmacyReportService(db, user).delete(year, week, pharmacy_id)


@router.get("/sales-index", response_model=list[PharmacySalesIndex],
            summary="Weekly sales index per category (public)")
def sales_index(municipality_id: int, weeks: int = Query(52, ge=4, le=520), category: str | None = Query(None),
                db: Session = Depends(get_db)):
    """100 = normal sales (mean of the previous 52 weeks). Aggregated data, nothing per pharmacy."""
    since = week_start(*shift(*last_complete_week(), -(weeks - 1)))
    rows = PharmacySource(db).fetch(municipality_id=municipality_id, categories=[category] if category else None,
                                    since=since)
    keys = ("year", "epi_week", "category", "units", "reporting_pharmacies", "sales_index")
    return [PharmacySalesIndex(label=label(r["year"], r["epi_week"]), **{k: r[k] for k in keys}) for r in rows]
