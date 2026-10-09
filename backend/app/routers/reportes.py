"""Reportes descargables (públicos: solo contienen datos agregados del dashboard)."""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Municipio
from app.services.reporte_service import ReporteService, nombre_archivo

router = APIRouter(prefix="/reportes", tags=["Reportes"])


def _descarga(contenido: bytes, tipo: str, archivo: str) -> Response:
    return Response(content=contenido, media_type=tipo,
                    headers={"Content-Disposition": f'attachment; filename="{archivo}"'})


@router.get("/casos.csv", summary="Casos semanales en CSV (filtros opcionales)")
def casos_csv(municipio_id: int | None = None, enfermedad_id: int | None = None,
              desde_anio: int | None = Query(None, ge=2000, le=2100), db: Session = Depends(get_db)):
    return _descarga(ReporteService(db).casos_csv(municipio_id, enfermedad_id, desde_anio), "text/csv; charset=utf-8",
                     nombre_archivo("casos", "csv"))


@router.get("/predicciones.csv", summary="Predicciones vigentes de las próximas 4 semanas en CSV")
def predicciones_csv(municipio_id: int | None = None, db: Session = Depends(get_db)):
    return _descarga(ReporteService(db).predicciones_csv(municipio_id), "text/csv; charset=utf-8",
                     nombre_archivo("predicciones", "csv"))


@router.get("/alertas.csv", summary="Historial de alertas en CSV")
def alertas_csv(solo_activas: bool = False, db: Session = Depends(get_db)):
    return _descarga(ReporteService(db).alertas_csv(solo_activas), "text/csv; charset=utf-8",
                     nombre_archivo("alertas", "csv"))


@router.get("/resumen.pdf", summary="Reporte PDF del municipio: semáforo, predicción, alertas, volcán y modelos")
def resumen_pdf(municipio_id: int, db: Session = Depends(get_db)):
    pdf = ReporteService(db).resumen_pdf(municipio_id)
    m = db.get(Municipio, municipio_id)
    return _descarga(pdf, "application/pdf", nombre_archivo("reporte-riesgo", "pdf", m.nombre if m else None))
