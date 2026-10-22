"""Búsquedas de síntomas: sincroniza Google Trends con la caché en BD y arma índices por enfermedad."""
import logging
from collections import defaultdict
from datetime import date, timedelta

from app.core.config import settings
from app.core.epi import etiqueta, inicio_semana, ultima_semana_completa
from app.fuentes import FuenteDatos, FuenteDatosError
from app.fuentes.trends import TrendsFuente
from app.models import Enfermedad
from app.repositories.repos import EnfermedadRepository, TendenciaRepository
from app.schemas.datos import PuntoTendencia, ResultadoTendencias, SerieTendencia

logger = logging.getLogger("predictor.trends")


class TendenciaService:
    def __init__(self, db, fuente: FuenteDatos | None = None, region: str | None = None):
        self.db = db
        self.fuente = fuente or TrendsFuente()
        self.region = region or settings.TRENDS_REGION
        self.repo = TendenciaRepository(db)
        self.enfermedades = EnfermedadRepository(db)

    def terminos(self) -> list[str]:
        """Términos de todas las enfermedades activas, sin repetir y en orden de aparición."""
        return list(dict.fromkeys(t for e in self.enfermedades.activas() for t in e.lista_terminos))

    def _esta_al_dia(self, termino: str) -> bool:
        ultimo = self.repo.ultima_real(termino, self.region)
        if ultimo is None:
            return False
        return ultimo.fecha_semana >= inicio_semana(*ultima_semana_completa()) - timedelta(days=7)

    def sincronizar(self, forzar: bool = False, desde: date | None = None) -> ResultadoTendencias:
        """Caché primero: solo consulta los términos que no tienen datos reales de la última semana."""
        terminos = self.terminos()
        al_dia = [] if forzar else [t for t in terminos if self._esta_al_dia(t)]
        pendientes = [t for t in terminos if t not in al_dia]
        if not pendientes:
            return ResultadoTendencias(fuente="cache", terminos=terminos, registros_guardados=0,
                                       desde_cache=al_dia, errores=[])
        desde = desde or date(settings.SEED_ANIO_INICIO, 1, 1) - timedelta(days=56)
        try:
            filas = self.fuente.obtener(terminos=pendientes, region=self.region, desde=desde)
        except FuenteDatosError as exc:
            logger.warning("Trends sin datos nuevos: %s", exc)
            return ResultadoTendencias(fuente="cache", terminos=terminos, registros_guardados=0,
                                       desde_cache=terminos, errores=[str(exc)])
        guardados = self.repo.upsert_lote(filas)
        return ResultadoTendencias(
            fuente=getattr(self.fuente, "ultima_fuente", None) or self.fuente.nombre, terminos=terminos,
            registros_guardados=guardados, desde_cache=al_dia, errores=[],
        )

    def serie(self, termino: str, semanas: int = 104) -> SerieTendencia:
        desde = inicio_semana(*ultima_semana_completa()) - timedelta(weeks=semanas)
        puntos = [
            PuntoTendencia(anio=t.anio, semana_epi=t.semana_epi, etiqueta=etiqueta(t.anio, t.semana_epi),
                           fecha_semana=t.fecha_semana, indice=t.indice, fuente=t.fuente, es_simulado=t.es_simulado)
            for t in self.repo.serie(termino.lower(), self.region, desde)
        ]
        return SerieTendencia(termino=termino.lower(), region=self.region, puntos=puntos)

    def indice_por_semana(self, enfermedad: Enfermedad, desde: date | None = None) -> dict[tuple[int, int], float]:
        """Promedio semanal del índice de todos los términos asociados a la enfermedad."""
        acumulado: dict[tuple[int, int], list[float]] = defaultdict(list)
        for termino in enfermedad.lista_terminos:
            for t in self.repo.serie(termino, self.region, desde):
                acumulado[(t.anio, t.semana_epi)].append(t.indice)
        return {k: sum(v) / len(v) for k, v in acumulado.items()}
