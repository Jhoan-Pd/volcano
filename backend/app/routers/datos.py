"""Fuentes de datos: sincronización manual (ADMIN) y consulta pública de las series."""
from fastapi import APIRouter, Depends, File, Path, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.deps import solo_admin
from app.db.session import get_db
from app.schemas.datos import EstadoDatos, ResultadoImportacion, ResultadoSivigila, ResultadoTendencias, SerieTendencia
from app.services.importacion_service import ImportacionService
from app.services.sivigila_service import SivigilaService
from app.services.tendencia_service import TendenciaService

router = APIRouter(prefix="/datos", tags=["Fuentes de datos"])


@router.post("/sincronizar/tendencias", response_model=ResultadoTendencias, dependencies=[Depends(solo_admin)],
             summary="Descargar búsquedas de Google Trends (caché en BD, respaldo CSV) — solo ADMIN")
def sincronizar_tendencias(forzar: bool = Query(False, description="Ignorar la caché y volver a consultar"),
                           db: Session = Depends(get_db)):
    return TendenciaService(db).sincronizar(forzar=forzar)


@router.get("/tendencias", response_model=SerieTendencia, summary="Serie semanal de búsquedas de un término")
def tendencias(termino: str = Query(..., min_length=2, max_length=60), semanas: int = Query(104, ge=4, le=520),
               db: Session = Depends(get_db)):
    return TendenciaService(db).serie(termino, semanas)


@router.post("/sincronizar/sivigila", response_model=ResultadoSivigila, dependencies=[Depends(solo_admin)],
             summary="Descargar casos oficiales de SIVIGILA (datos.gov.co) — solo ADMIN")
def sincronizar_sivigila(desde_anio: int = Query(2020, ge=2007, le=2100), db: Session = Depends(get_db)):
    """Usa los códigos INS configurados en cada enfermedad (`codigos_sivigila`).
    Los datos oficiales reemplazan a los simulados de las mismas semanas."""
    return SivigilaService(db).sincronizar(desde_anio)


@router.post("/importar/{tipo}", response_model=ResultadoImportacion, dependencies=[Depends(solo_admin)],
             summary="Cargar un CSV de casos, clima, eventos volcánicos o búsquedas — solo ADMIN")
async def importar_csv(tipo: str = Path(..., pattern="^(casos|clima|eventos|tendencias)$"),
                       archivo: UploadFile = File(..., description="CSV con encabezados; separador , o ;"),
                       db: Session = Depends(get_db)):
    """Inserta o actualiza (no duplica). Las filas con error se informan con su número de línea.

    - **casos**: `cod_divipola, enfermedad, anio, semana_epi, casos`
    - **clima**: `cod_divipola, fecha, temp_max_c, temp_min_c, temp_media_c, precipitacion_mm, humedad_relativa_pct`
    - **eventos**: `tipo, nivel_actividad, fecha_inicio, cod_divipola, intensidad_ceniza, so2_ton_dia, descripcion`
    - **tendencias**: `termino, fecha_semana, indice`
    """
    return ImportacionService(db).importar(tipo, await archivo.read())


@router.get("/estado", response_model=EstadoDatos, dependencies=[Depends(solo_admin)],
            summary="Registros, datos simulados y última actualización de cada fuente — solo ADMIN")
def estado(db: Session = Depends(get_db)):
    return ImportacionService(db).estado()
