"""Arma la información del dashboard público a partir de las series guardadas."""
from datetime import date, timedelta

from sqlalchemy import select

from app.core.epi import desplazar, etiqueta, inicio_semana, iterar_semanas
from app.core.errors import NoEncontradoError
from app.models import CasoOficial, Enfermedad, Municipio
from app.repositories.repos import (
    CasoOficialRepository, EnfermedadRepository, EventoVolcanicoRepository, MunicipioRepository,
)
from app.schemas.dashboard import (
    EstadoVolcan, EventoCeniza, PuntoSerie, ResumenDashboard, RiesgoEnfermedad, RiesgoMunicipio,
    SerieEnfermedad, Umbrales,
)
from app.services import riesgo_service as rs
from app.services.prediccion_service import PrediccionService


class DashboardService:
    def __init__(self, db):
        self.db = db
        self.municipios = MunicipioRepository(db)
        self.enfermedades = EnfermedadRepository(db)
        self.casos = CasoOficialRepository(db)
        self.eventos = EventoVolcanicoRepository(db)
        self.predicciones = PrediccionService(db)

    # ── utilidades ──────────────────────────────────────────────────────────
    def _municipio(self, municipio_id: int | None) -> Municipio:
        if municipio_id is None:
            activos = self.municipios.activos()
            if not activos:
                raise NoEncontradoError("No hay municipios cargados. Ejecuta el seed.")
            return activos[0]
        m = self.municipios.obtener(municipio_id)
        if m is None:
            raise NoEncontradoError(f"Municipio {municipio_id} no existe")
        return m

    def _serie_dict(self, municipio_id: int, enfermedad_id: int) -> tuple[dict[tuple[int, int], int], bool]:
        filas = self.db.execute(
            select(CasoOficial.anio, CasoOficial.semana_epi, CasoOficial.casos, CasoOficial.es_simulado)
            .where(CasoOficial.municipio_id == municipio_id, CasoOficial.enfermedad_id == enfermedad_id)
        ).all()
        return {(a, s): c for a, s, c, _ in filas}, any(f[3] for f in filas)

    @staticmethod
    def _umbrales(serie: dict, enf: Enfermedad, anio: int, semana: int) -> rs.UmbralesCanal | None:
        valores = [serie[p] for p in rs.semanas_referencia(anio, semana) if p in serie]
        return rs.calcular_umbrales(valores, enf.umbral_amarillo_pct, enf.umbral_naranja_pct, enf.umbral_rojo_pct)

    def _semana_referencia(self) -> tuple[int, int]:
        ref = self.casos.ultima_semana()
        if ref is None:
            raise NoEncontradoError("No hay casos registrados. Ejecuta el seed.")
        return ref

    # ── casos de uso ────────────────────────────────────────────────────────
    def riesgo_enfermedad(self, m: Municipio, enf: Enfermedad, anio: int, semana: int) -> RiesgoEnfermedad:
        serie, simulado = self._serie_dict(m.id, enf.id)
        casos = serie.get((anio, semana), 0)
        previa = serie.get(desplazar(anio, semana, -1))
        u = self._umbrales(serie, enf, anio, semana)
        nivel = rs.clasificar(casos, u)
        variacion = None
        if previa:
            variacion = round((casos - previa) / previa * 100, 1)
        return RiesgoEnfermedad(
            enfermedad_id=enf.id, codigo=enf.codigo, nombre=enf.nombre, color=enf.color,
            anio=anio, semana_epi=semana, casos=casos, casos_semana_anterior=previa,
            variacion_pct=variacion, tasa_x_100k=round(casos / m.poblacion * 100_000, 2),
            umbrales=Umbrales(amarillo=u.amarillo, naranja=u.naranja, rojo=u.rojo) if u
            else Umbrales(amarillo=0, naranja=0, rojo=0),
            nivel=nivel.value, es_simulado=simulado,
            recomendaciones=[r.strip() for r in (enf.recomendaciones or "").splitlines() if r.strip()],
            prediccion=self.predicciones.resumen(m.id, enf.id),
        )

    def estado_volcan(self, hoy: date | None = None) -> EstadoVolcan:
        hoy = hoy or date.today()
        b = self.eventos.ultimo_boletin()
        cenizas = self.eventos.cenizas_desde(hoy - timedelta(days=365))[:5]
        return EstadoVolcan(
            nivel_actividad=b.nivel_actividad if b else "SIN_DATO",
            fecha=b.fecha_inicio if b else None,
            descripcion=b.descripcion if b else None,
            url_boletin=b.url_boletin if b else None,
            es_simulado=b.es_simulado if b else True,
            so2_ton_dia=b.so2_ton_dia if b else None,
            ceniza_reciente=[
                EventoCeniza(fecha=e.fecha_inicio, municipio=e.municipio.nombre if e.municipio else None,
                             intensidad=e.intensidad_ceniza, descripcion=e.descripcion, es_simulado=e.es_simulado)
                for e in cenizas
            ],
        )

    def resumen(self, municipio_id: int | None) -> ResumenDashboard:
        m = self._municipio(municipio_id)
        anio, semana = self._semana_referencia()
        riesgos = [self.riesgo_enfermedad(m, e, anio, semana) for e in self.enfermedades.activas()]
        volcan = self.estado_volcan()
        return ResumenDashboard(
            municipio_id=m.id, municipio=m.nombre, poblacion=m.poblacion,
            semana_referencia=etiqueta(anio, semana), riesgos=riesgos, volcan=volcan,
            hay_datos_simulados=any(r.es_simulado for r in riesgos) or volcan.es_simulado,
        )

    def serie(self, municipio_id: int, enfermedad_id: int, semanas: int = 104) -> SerieEnfermedad:
        m = self._municipio(municipio_id)
        enf = self.enfermedades.obtener(enfermedad_id)
        if enf is None:
            raise NoEncontradoError(f"Enfermedad {enfermedad_id} no existe")
        serie, _ = self._serie_dict(m.id, enf.id)
        fin = self._semana_referencia()
        ini = desplazar(*fin, -(semanas - 1))
        puntos = []
        for a, s in iterar_semanas(ini, fin):
            u = self._umbrales(serie, enf, a, s)
            puntos.append(PuntoSerie(
                anio=a, semana_epi=s, etiqueta=etiqueta(a, s), fecha_inicio=inicio_semana(a, s),
                casos=serie.get((a, s)),
                p_amarillo=u.amarillo if u else None, p_naranja=u.naranja if u else None,
                p_rojo=u.rojo if u else None,
            ))
        return SerieEnfermedad(municipio_id=m.id, enfermedad_id=enf.id, enfermedad=enf.nombre, puntos=puntos)

    def riesgo_por_municipio(self) -> list[RiesgoMunicipio]:
        anio, semana = self._semana_referencia()
        enfermedades = self.enfermedades.activas()
        salida = []
        for m in self.municipios.activos():
            riesgos = [self.riesgo_enfermedad(m, e, anio, semana) for e in enfermedades]
            detalle = {r.codigo: r.nivel for r in riesgos}
            predicho = {r.codigo: r.prediccion.nivel_max for r in riesgos if r.prediccion}
            salida.append(RiesgoMunicipio(
                municipio_id=m.id, municipio=m.nombre, codigo_divipola=m.codigo_divipola,
                latitud=m.latitud, longitud=m.longitud,
                nivel_max=rs.nivel_maximo(list(detalle.values())), detalle=detalle,
                nivel_max_predicho=rs.nivel_maximo(list(predicho.values())) if predicho else None,
                detalle_predicho=predicho,
            ))
        return salida
