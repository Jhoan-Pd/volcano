"""Data sources: manual synchronization (ADMIN) and public trend series."""
from fastapi import APIRouter, Depends, File, Path, Query, UploadFile
from sqlalchemy.orm import Session

from volcano.db.session import get_db
from volcano.gateway.deps import admin_only
from volcano.schemas.data_sources import DataStatus, ImportResult, SivigilaSyncResult, TrendSeries, TrendSyncResult
from volcano.services.csv_import import CsvImportService
from volcano.services.search_trends import SearchTrendService
from volcano.services.sivigila import SivigilaService

router = APIRouter(prefix="/data", tags=["Data sources"])


@router.post("/trends/sync", response_model=TrendSyncResult, dependencies=[Depends(admin_only)],
             summary="Download Google Trends searches (DB cache, CSV fallback) — ADMIN only")
def sync_trends(force: bool = Query(False, description="Ignore the cache and query again"),
                db: Session = Depends(get_db)):
    return SearchTrendService(db).sync(force=force)


@router.get("/trends", response_model=TrendSeries, summary="Weekly search series of one term")
def trends(term: str = Query(..., min_length=2, max_length=60), weeks: int = Query(104, ge=4, le=520),
           db: Session = Depends(get_db)):
    return SearchTrendService(db).series(term, weeks)


@router.post("/sivigila/sync", response_model=SivigilaSyncResult, dependencies=[Depends(admin_only)],
             summary="Download official SIVIGILA cases (datos.gov.co) — ADMIN only")
def sync_sivigila(since_year: int = Query(2020, ge=2007, le=2100), db: Session = Depends(get_db)):
    """Uses the INS codes configured on each disease (`sivigila_codes`). Official data replaces the
    simulated data of the same weeks."""
    return SivigilaService(db).sync(since_year)


@router.post("/import/{kind}", response_model=ImportResult, dependencies=[Depends(admin_only)],
             summary="Upload a CSV of cases, weather, volcanic events or searches — ADMIN only")
async def import_csv(kind: str = Path(..., pattern="^(cases|weather|events|trends)$"),
                     file: UploadFile = File(..., description="CSV with headers; separator , or ;"),
                     db: Session = Depends(get_db)):
    """Inserts or updates (never duplicates). Rows with errors are reported with their line number.

    - **cases**: `divipola_code, disease, year, epi_week, cases`
    - **weather**: `divipola_code, date, temp_max_c, temp_min_c, temp_mean_c, precipitation_mm, relative_humidity_pct`
    - **events**: `event_type, activity_level, start_date, divipola_code, ash_intensity, so2_tons_per_day, description`
    - **trends**: `term, week_start, interest`
    """
    return CsvImportService(db).import_file(kind, await file.read())


@router.get("/status", response_model=DataStatus, dependencies=[Depends(admin_only)],
            summary="Rows, simulated rows and last update of every source — ADMIN only")
def status(db: Session = Depends(get_db)):
    return CsvImportService(db).status()
