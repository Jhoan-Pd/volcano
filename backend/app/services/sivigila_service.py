"""Casos oficiales: sincroniza SIVIGILA (datos.gov.co) con la tabla casos_oficiales.

Regla: un dato oficial reemplaza al simulado de la misma semana. Como Socrata solo publica
las semanas con casos, en los años que el dataset sí cubre las semanas ausentes se guardan
con 0 casos (también como dato oficial).
"""
import logging
from collections import defaultdict

from app.core.config import settings
from app.core.epi import semanas_del_anio
from app.fuentes import FuenteDatos, FuenteDatosError
from app.fuentes.sivigila import SivigilaFuente
from app.repositories.repos import CasoOficialRepository, EnfermedadRepository, MunicipioRepository
from app.schemas.datos import ResultadoSivigila

logger = logging.getLogger("predictor.sivigila")


class SivigilaService:
    def __init__(self, db, fuente: FuenteDatos | None = None):
        self.db = db
        self.fuente = fuente or SivigilaFuente()
        self.casos = CasoOficialRepository(db)
        self.enfermedades = EnfermedadRepository(db)
        self.municipios = MunicipioRepository(db)

    def sincronizar(self, desde_anio: int | None = None) -> ResultadoSivigila:
        desde_anio = desde_anio or settings.SEED_ANIO_INICIO
        municipios = {m.codigo_divipola: m.id for m in self.municipios.activos()}
        nombres, anios_total, errores = [], set(), []
        guardadas = con_casos = 0
        for enf in self.enfermedades.activas():
            codigos = enf.lista_codigos_sivigila
            if not codigos:
                continue
            nombres.append(enf.codigo)
            try:
                filas = self.fuente.obtener(codigos_evento=codigos, desde_anio=desde_anio)
            except (FuenteDatosError, ValueError) as exc:
                logger.warning("SIVIGILA %s: %s", enf.codigo, exc)
                errores.append(f"{enf.codigo}: {exc}")
                continue
            # Años cubiertos = años con al menos un registro en el departamento
            anios = sorted({f["anio"] for f in filas if f["anio"] >= desde_anio})
            suma: dict[tuple[str, int, int], int] = defaultdict(int)
            for f in filas:
                suma[(f["cod_divipola"], f["anio"], f["semana_epi"])] += f["casos"]
            lote = []
            for divipola, mid in municipios.items():
                for anio in anios:
                    for semana in range(1, semanas_del_anio(anio) + 1):
                        casos = suma.get((divipola, anio, semana), 0)
                        con_casos += casos > 0
                        lote.append({"municipio_id": mid, "enfermedad_id": enf.id, "anio": anio, "semana_epi": semana,
                                     "casos": casos, "fuente": self.fuente.nombre, "es_simulado": False})
            ins, act = self.casos.upsert_lote(lote)
            guardadas += ins + act
            anios_total.update(anios)
        return ResultadoSivigila(enfermedades=nombres, anios_cubiertos=sorted(anios_total),
                                 registros_guardados=guardadas, semanas_con_casos=con_casos, errores=errores)
