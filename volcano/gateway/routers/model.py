"""Predictive model: retraining (ADMIN), status, history and metrics.

Training and prediction run in the engine; these endpoints delegate to it over gRPC (unary calls).
"""
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from volcano.db.session import get_db
from volcano.gateway.deps import admin_only
from volcano.rpc.client import EngineClient, engine_client
from volcano.schemas.engine import RefreshResultOut
from volcano.schemas.model import ModelOut, TrainingStatus
from volcano.services.predictions import PredictionQueryService

router = APIRouter(prefix="/model", tags=["Predictive model"])


@router.post("/retrain", response_model=TrainingStatus, status_code=status.HTTP_202_ACCEPTED,
             dependencies=[Depends(admin_only)], summary="Retrain the models (in the background) — ADMIN only")
async def retrain(disease_id: int | None = Query(None, description="Empty = every disease"),
                  engine: EngineClient = Depends(engine_client)):
    """Compares the moving average, Random Forest and Gradient Boosting; keeps the best one with its
    metrics and regenerates the predictions. Poll `GET /model/status` or use `POST /engine/training`
    to watch it live."""
    return await engine.start_training(disease_id)


@router.get("/status", response_model=TrainingStatus, dependencies=[Depends(admin_only)],
            summary="Status of the latest retraining")
async def training_status(engine: EngineClient = Depends(engine_client)):
    return await engine.training_status()


@router.post("/predict", response_model=RefreshResultOut, dependencies=[Depends(admin_only)],
             summary="Regenerate predictions with the active models")
async def predict(engine: EngineClient = Depends(engine_client)):
    return await engine.refresh_forecasts(evaluate_alerts=False)


@router.get("/history", response_model=list[ModelOut], summary="Trained models with date and metrics (public)")
def history(disease_id: int | None = Query(None), limit: int = Query(50, ge=1, le=500), db: Session = Depends(get_db)):
    return PredictionQueryService(db).history(disease_id, limit)
