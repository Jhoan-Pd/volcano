"""Public dashboard endpoints (no login required)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from volcano.db.session import get_db
from volcano.schemas.dashboard import DashboardSummary, DiseaseSeries, MunicipalityRisk, VolcanoStatus
from volcano.schemas.model import DiseasePrediction, PredictionExplanation
from volcano.services.dashboard import DashboardService
from volcano.services.predictions import PredictionQueryService

router = APIRouter(prefix="/dashboard", tags=["Public dashboard"])


@router.get("/summary", response_model=DashboardSummary, summary="Traffic light per disease + volcano status")
def summary(municipality_id: int | None = Query(None, description="Defaults to the first municipality (Pasto)"),
            db: Session = Depends(get_db)):
    return DashboardService(db).summary(municipality_id)


@router.get("/series", response_model=DiseaseSeries, summary="Weekly series with the endemic channel")
def series(municipality_id: int, disease_id: int, weeks: int = Query(104, ge=8, le=520),
           db: Session = Depends(get_db)):
    return DashboardService(db).series(municipality_id, disease_id, weeks)


@router.get("/municipality-risk", response_model=list[MunicipalityRisk], summary="Risk level of every municipality")
def municipality_risk(db: Session = Depends(get_db)):
    return DashboardService(db).risk_by_municipality()


@router.get("/volcano", response_model=VolcanoStatus, summary="Current status of the Galeras volcano")
def volcano(db: Session = Depends(get_db)):
    return DashboardService(db).volcano_status()


@router.get("/prediction", response_model=DiseasePrediction,
            summary="Expected cases for the next 4 weeks with an 80 % interval and risk level")
def prediction(municipality_id: int, disease_id: int, db: Session = Depends(get_db)):
    return PredictionQueryService(db).prediction(municipality_id, disease_id)


@router.get("/explanation", response_model=PredictionExplanation, summary="Why did the risk go up? (explainability)")
def explanation(municipality_id: int, disease_id: int, horizon: int | None = Query(None, ge=1, le=4),
                db: Session = Depends(get_db)):
    return PredictionQueryService(db).explanation(municipality_id, disease_id, horizon)
