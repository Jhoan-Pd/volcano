"""Panel de farmacia: reporte semanal de ventas por categoría (roles FARMACIA y ADMIN)."""
from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app.core.deps import requiere_roles
from app.core.epi import desplazar, etiqueta, inicio_semana, ultima_semana_completa
from app.db.session import get_db
from app.fuentes.farmacia import FarmaciaFuente
from app.models import Usuario
from app.models.enums import RolNombre
from app.schemas.farmacia import IndiceFarmacia, MiFarmacia, ReporteSemanalIn, ReporteSemanalOut, ReporteSemanalUpdate
from app.services.reporte_farmacia_service import ReporteFarmaciaService

router = APIRouter(prefix="/farmacia", tags=["Farmacias (reportes)"])
farmacia_o_admin = requiere_roles(RolNombre.FARMACIA, RolNombre.ADMIN)


@router.get("/mi-farmacia", response_model=MiFarmacia, summary="Datos de mi farmacia y semanas que puedo reportar")
def mi_farmacia(farmacia_id: int | None = Query(None, description="Solo ADMIN"), db: Session = Depends(get_db),
                usuario: Usuario = Depends(farmacia_o_admin)):
    return ReporteFarmaciaService(db, usuario).mi_farmacia(farmacia_id)


@router.get("/reportes", response_model=list[ReporteSemanalOut], summary="Historial de reportes (más reciente primero)")
def historial(farmacia_id: int | None = Query(None), semanas: int = Query(26, ge=1, le=260),
              db: Session = Depends(get_db), usuario: Usuario = Depends(farmacia_o_admin)):
    return ReporteFarmaciaService(db, usuario).historial(farmacia_id, semanas)


@router.get("/reportes/{anio}/{semana}", response_model=ReporteSemanalOut, summary="Reporte de una semana")
def obtener(anio: int = Path(ge=2015, le=2100), semana: int = Path(ge=1, le=53), farmacia_id: int | None = Query(None),
            db: Session = Depends(get_db), usuario: Usuario = Depends(farmacia_o_admin)):
    return ReporteFarmaciaService(db, usuario).obtener(anio, semana, farmacia_id)


@router.post("/reportes", response_model=ReporteSemanalOut, status_code=status.HTTP_201_CREATED,
             summary="Registrar el reporte de una semana")
def crear(entrada: ReporteSemanalIn, db: Session = Depends(get_db), usuario: Usuario = Depends(farmacia_o_admin)):
    return ReporteFarmaciaService(db, usuario).crear(entrada)


@router.put("/reportes/{anio}/{semana}", response_model=ReporteSemanalOut, summary="Corregir el reporte de una semana")
def actualizar(entrada: ReporteSemanalUpdate, anio: int = Path(ge=2015, le=2100), semana: int = Path(ge=1, le=53),
               farmacia_id: int | None = Query(None), db: Session = Depends(get_db),
               usuario: Usuario = Depends(farmacia_o_admin)):
    return ReporteFarmaciaService(db, usuario).actualizar(anio, semana, entrada.items, farmacia_id)


@router.delete("/reportes/{anio}/{semana}", status_code=status.HTTP_204_NO_CONTENT, summary="Eliminar el reporte de una semana")
def eliminar(anio: int = Path(ge=2015, le=2100), semana: int = Path(ge=1, le=53), farmacia_id: int | None = Query(None),
             db: Session = Depends(get_db), usuario: Usuario = Depends(farmacia_o_admin)):
    ReporteFarmaciaService(db, usuario).eliminar(anio, semana, farmacia_id)


@router.get("/indice", response_model=list[IndiceFarmacia], summary="Índice semanal de ventas por categoría (público)")
def indice(municipio_id: int, semanas: int = Query(52, ge=4, le=520), categoria: str | None = Query(None),
           db: Session = Depends(get_db)):
    """100 = ventas normales (promedio de las 52 semanas anteriores). Datos agregados, sin detalle por farmacia."""
    desde = inicio_semana(*desplazar(*ultima_semana_completa(), -(semanas - 1)))
    filas = FarmaciaFuente(db).obtener(municipio_id=municipio_id, categorias=[categoria] if categoria else None,
                                       desde=desde)
    return [IndiceFarmacia(etiqueta=etiqueta(f["anio"], f["semana_epi"]), **{k: f[k] for k in (
        "anio", "semana_epi", "categoria", "unidades", "farmacias_reportando", "indice")}) for f in filas]
