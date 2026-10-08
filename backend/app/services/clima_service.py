"""Clima: sincroniza Open-Meteo con la BD y entrega clima actual, pronóstico e histórico semanal."""
import logging
import time
from collections import defaultdict
from datetime import date, timedelta

from app.core.epi import desplazar, etiqueta, inicio_semana, semana_de, ultima_semana_completa
from app.core.errors import NoEncontradoError
from app.fuentes import FuenteDatos, FuenteDatosError, OpenMeteoFuente
from app.models import Municipio
from app.repositories.repos import MunicipioRepository, RegistroClimaRepository
from app.schemas.clima import ClimaActual, ClimaDiario, ClimaSemanal, ResultadoSincronizacion

logger = logging.getLogger("predictor.clima")

# Caché en memoria del clima actual: evita llamar a Open-Meteo en cada visita al dashboard
_CACHE_ACTUAL: dict[int, tuple[float, ClimaActual]] = {}
TTL_ACTUAL_SEG = 600


class ClimaService:
    def __init__(self, db, fuente: FuenteDatos | None = None):
        self.db = db
        self.fuente: OpenMeteoFuente = fuente or OpenMeteoFuente()  # Strategy inyectable (tests usan un doble)
        self.municipios = MunicipioRepository(db)
        self.registros = RegistroClimaRepository(db)

    def _municipio(self, municipio_id: int) -> Municipio:
        m = self.municipios.obtener(municipio_id)
        if m is None:
            raise NoEncontradoError(f"Municipio {municipio_id} no existe")
        return m

    # ── Sincronización ──────────────────────────────────────────────────────
    def sincronizar_municipio(self, m: Municipio, dias_pasados: int = 14) -> int:
        filas = self.fuente.obtener(latitud=m.latitud, longitud=m.longitud, modo="pronostico",
                                    dias_pasados=dias_pasados)
        return self.registros.upsert_lote(m.id, filas)

    def sincronizar(self, dias_pasados: int = 14) -> ResultadoSincronizacion:
        total, errores = 0, []
        municipios = self.municipios.activos()
        for m in municipios:
            try:
                total += self.sincronizar_municipio(m, dias_pasados)
            except FuenteDatosError as exc:
                logger.warning("Clima %s: %s", m.nombre, exc)
                errores.append(f"{m.nombre}: {exc}")
        return ResultadoSincronizacion(municipios=len(municipios), registros_guardados=total, errores=errores)

    def cargar_historico_real(self, m: Municipio, desde: date, hasta: date) -> int:
        filas = self.fuente.obtener(latitud=m.latitud, longitud=m.longitud, modo="historico",
                                    desde=desde, hasta=hasta)
        return self.registros.upsert_lote(m.id, filas)

    # ── Consultas ───────────────────────────────────────────────────────────
    def actual(self, municipio_id: int) -> ClimaActual:
        m = self._municipio(municipio_id)
        cache = _CACHE_ACTUAL.get(m.id)
        if cache and time.time() - cache[0] < TTL_ACTUAL_SEG:
            return cache[1]
        try:
            datos = self.fuente.actual(latitud=m.latitud, longitud=m.longitud)
            res = ClimaActual(municipio_id=m.id, municipio=m.nombre, fuente="open-meteo", **datos)
            _CACHE_ACTUAL[m.id] = (time.time(), res)
            return res
        except FuenteDatosError as exc:
            # Fallback: último registro observado en BD (el dashboard nunca queda vacío)
            logger.warning("Clima actual en vivo falló (%s); usando BD", exc)
            r = self.registros.ultimo_observado(m.id)
            return ClimaActual(
                municipio_id=m.id, municipio=m.nombre, hora=None,
                temperatura_c=r.temp_media_c if r else None,
                humedad_relativa_pct=r.humedad_relativa_pct if r else None,
                precipitacion_mm=r.precipitacion_mm if r else None, viento_kmh=None, codigo_tiempo=None,
                descripcion=f"Último registro guardado ({r.fecha.isoformat()})" if r else "Sin datos",
                fuente="bd",
            )

    def pronostico(self, municipio_id: int, dias: int = 16) -> list[ClimaDiario]:
        m = self._municipio(municipio_id)
        hoy = date.today()
        filas = self.registros.rango(m.id, hoy, hoy + timedelta(days=dias - 1))
        if len(filas) < min(dias, 7):
            # No hay pronóstico fresco: se intenta traer de Open-Meteo en el momento
            try:
                self.sincronizar_municipio(m, dias_pasados=1)
                filas = self.registros.rango(m.id, hoy, hoy + timedelta(days=dias - 1))
            except FuenteDatosError as exc:
                logger.warning("No se pudo actualizar el pronóstico: %s", exc)
        return [ClimaDiario.model_validate(f) for f in filas]

    def semanal(self, municipio_id: int, semanas: int = 52) -> list[ClimaSemanal]:
        """Agrega el clima diario observado a semanas epidemiológicas."""
        m = self._municipio(municipio_id)
        fin = ultima_semana_completa()
        ini = desplazar(*fin, -(semanas - 1))
        desde = inicio_semana(*ini)
        filas = [f for f in self.registros.rango(m.id, desde) if not f.es_pronostico]
        grupos: dict[tuple[int, int], list] = defaultdict(list)
        for f in filas:
            grupos[semana_de(f.fecha)].append(f)

        def prom(vals):
            vals = [v for v in vals if v is not None]
            return round(sum(vals) / len(vals), 2) if vals else None

        salida = []
        for (a, s), regs in sorted(grupos.items()):
            if (a, s) > fin:
                continue
            lluvia = [r.precipitacion_mm for r in regs if r.precipitacion_mm is not None]
            salida.append(ClimaSemanal(
                anio=a, semana_epi=s, etiqueta=etiqueta(a, s),
                temp_media_c=prom([r.temp_media_c for r in regs]),
                precipitacion_mm=round(sum(lluvia), 1) if lluvia else None,
                humedad_relativa_pct=prom([r.humedad_relativa_pct for r in regs]),
            ))
        return salida
