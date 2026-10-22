"""Repositorios concretos por entidad."""
from datetime import date

from sqlalchemy import and_, or_, select
from app.models import (
    CasoOficial, Enfermedad, EventoVolcanico, Farmacia, Municipio, RegistroClima, Rol, TendenciaBusqueda,
    Usuario,
)
from app.repositories.base import BaseRepository


class RolRepository(BaseRepository[Rol]):
    model = Rol

    def por_nombre(self, nombre: str) -> Rol | None:
        return self.obtener_por(nombre=nombre)


class UsuarioRepository(BaseRepository[Usuario]):
    model = Usuario

    def por_email(self, email: str) -> Usuario | None:
        return self.db.scalars(select(Usuario).where(Usuario.email == email.lower())).first()


class MunicipioRepository(BaseRepository[Municipio]):
    model = Municipio

    def activos(self) -> list[Municipio]:
        return list(self.db.scalars(select(Municipio).where(Municipio.activo.is_(True)).order_by(Municipio.id)))


class EnfermedadRepository(BaseRepository[Enfermedad]):
    model = Enfermedad

    def activas(self) -> list[Enfermedad]:
        return list(self.db.scalars(select(Enfermedad).where(Enfermedad.activo.is_(True)).order_by(Enfermedad.id)))


class FarmaciaRepository(BaseRepository[Farmacia]):
    model = Farmacia


class EventoVolcanicoRepository(BaseRepository[EventoVolcanico]):
    model = EventoVolcanico

    def ultimo_boletin(self) -> EventoVolcanico | None:
        stmt = (select(EventoVolcanico).where(EventoVolcanico.tipo == "BOLETIN")
                .order_by(EventoVolcanico.fecha_inicio.desc(), EventoVolcanico.id.desc()).limit(1))
        return self.db.scalars(stmt).first()

    def cenizas_desde(self, desde: date, municipio_id: int | None = None) -> list[EventoVolcanico]:
        stmt = select(EventoVolcanico).where(
            EventoVolcanico.tipo == "CAIDA_CENIZA", EventoVolcanico.fecha_inicio >= desde
        )
        if municipio_id:
            stmt = stmt.where(EventoVolcanico.municipio_id == municipio_id)
        return list(self.db.scalars(stmt.order_by(EventoVolcanico.fecha_inicio.desc())).unique())


class RegistroClimaRepository(BaseRepository[RegistroClima]):
    model = RegistroClima

    def rango(self, municipio_id: int, desde: date, hasta: date | None = None) -> list[RegistroClima]:
        stmt = select(RegistroClima).where(RegistroClima.municipio_id == municipio_id, RegistroClima.fecha >= desde)
        if hasta:
            stmt = stmt.where(RegistroClima.fecha <= hasta)
        return list(self.db.scalars(stmt.order_by(RegistroClima.fecha)))

    def ultimo_observado(self, municipio_id: int) -> RegistroClima | None:
        stmt = (select(RegistroClima)
                .where(RegistroClima.municipio_id == municipio_id, RegistroClima.es_pronostico.is_(False))
                .order_by(RegistroClima.fecha.desc()).limit(1))
        return self.db.scalars(stmt).first()

    def upsert_lote(self, municipio_id: int, filas: list[dict]) -> int:
        """Inserta o actualiza los días de un municipio por (municipio_id, fecha). Devuelve cuántos guardó."""
        filas = [{**f, "municipio_id": municipio_id} for f in filas]
        ins, act = self.upsert(filas, ("municipio_id", "fecha"), [
            RegistroClima.municipio_id == municipio_id, RegistroClima.fecha.in_([f["fecha"] for f in filas])])
        return ins + act


class CasoOficialRepository(BaseRepository[CasoOficial]):
    model = CasoOficial

    def serie(self, municipio_id: int, enfermedad_id: int) -> list[CasoOficial]:
        stmt = (select(CasoOficial)
                .where(CasoOficial.municipio_id == municipio_id, CasoOficial.enfermedad_id == enfermedad_id)
                .order_by(CasoOficial.anio, CasoOficial.semana_epi))
        return list(self.db.scalars(stmt))

    def ultima_semana(self) -> tuple[int, int] | None:
        stmt = select(CasoOficial.anio, CasoOficial.semana_epi).order_by(
            CasoOficial.anio.desc(), CasoOficial.semana_epi.desc()).limit(1)
        fila = self.db.execute(stmt).first()
        return (fila[0], fila[1]) if fila else None

    def upsert_lote(self, filas: list[dict]) -> tuple[int, int]:
        """Inserta o actualiza por (municipio, enfermedad, año, semana). Devuelve (insertadas, actualizadas)."""
        return self.upsert(filas, ("municipio_id", "enfermedad_id", "anio", "semana_epi"), [
            CasoOficial.municipio_id.in_({f["municipio_id"] for f in filas}),
            CasoOficial.enfermedad_id.in_({f["enfermedad_id"] for f in filas}),
            CasoOficial.anio.in_({f["anio"] for f in filas}),
        ])

    def semanas(self, municipio_id: int, enfermedad_id: int, pares: list[tuple[int, int]]) -> list[CasoOficial]:
        if not pares:
            return []
        cond = or_(*[and_(CasoOficial.anio == a, CasoOficial.semana_epi == s) for a, s in pares])
        stmt = select(CasoOficial).where(
            CasoOficial.municipio_id == municipio_id, CasoOficial.enfermedad_id == enfermedad_id, cond)
        return list(self.db.scalars(stmt))



class TendenciaRepository(BaseRepository[TendenciaBusqueda]):
    model = TendenciaBusqueda

    def serie(self, termino: str, region: str, desde: date | None = None) -> list[TendenciaBusqueda]:
        stmt = select(TendenciaBusqueda).where(TendenciaBusqueda.termino == termino,
                                               TendenciaBusqueda.region == region)
        if desde:
            stmt = stmt.where(TendenciaBusqueda.fecha_semana >= desde)
        return list(self.db.scalars(stmt.order_by(TendenciaBusqueda.fecha_semana)))

    def ultima_real(self, termino: str, region: str) -> TendenciaBusqueda | None:
        """Último registro que vino de una fuente real (pytrends o CSV), no simulado."""
        stmt = (select(TendenciaBusqueda)
                .where(TendenciaBusqueda.termino == termino, TendenciaBusqueda.region == region,
                       TendenciaBusqueda.es_simulado.is_(False))
                .order_by(TendenciaBusqueda.fecha_semana.desc()).limit(1))
        return self.db.scalars(stmt).first()

    def upsert_lote(self, filas: list[dict]) -> int:
        """Inserta o actualiza por (termino, region, anio, semana_epi). Devuelve cuántas guardó."""
        ins, act = self.upsert(filas, ("termino", "region", "anio", "semana_epi"),
                               [TendenciaBusqueda.termino.in_({f["termino"] for f in filas})])
        return ins + act
