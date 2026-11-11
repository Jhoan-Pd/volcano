from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from volcano.db.session import get_db
from volcano.gateway.deps import admin_only
from volcano.schemas.weather import CurrentWeather, DailyWeather, WeatherSyncResult, WeeklyWeather
from volcano.services.weather import WeatherService

router = APIRouter(prefix="/weather", tags=["Weather (Open-Meteo)"])


@router.get("/{municipality_id}/current", response_model=CurrentWeather, summary="Current weather (live, cached)")
def current(municipality_id: int, db: Session = Depends(get_db)):
    return WeatherService(db).current(municipality_id)


@router.get("/{municipality_id}/forecast", response_model=list[DailyWeather], summary="Daily forecast (up to 16 days)")
def forecast(municipality_id: int, days: int = Query(16, ge=1, le=16), db: Session = Depends(get_db)):
    return WeatherService(db).forecast(municipality_id, days)


@router.get("/{municipality_id}/weekly", response_model=list[WeeklyWeather],
            summary="Observed weather per epidemiological week")
def weekly(municipality_id: int, weeks: int = Query(52, ge=1, le=520), db: Session = Depends(get_db)):
    return WeatherService(db).weekly(municipality_id, weeks)


@router.post("/sync", response_model=WeatherSyncResult, dependencies=[Depends(admin_only)],
             summary="Download the forecast and the last days from Open-Meteo — ADMIN only")
def sync(past_days: int = Query(14, ge=0, le=92), db: Session = Depends(get_db)):
    return WeatherService(db).sync(past_days)
