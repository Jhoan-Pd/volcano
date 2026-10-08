"""Repositorios concretos por entidad."""
from datetime import date

from sqlalchemy import and_, or_, select
from app.models import (
    CasoOficial, Enfermedad, EventoVolcanico, Farmacia, Municipio, RegistroClima, Rol, Usuario,
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
        """Inserta o actualiza por (municipio_id, fecha). Portable entre SQLite y PostgreSQL."""
        if not filas:
            return 0
        fechas = [f["fecha"] for f in filas]
        existentes = {
            r.fecha: r for r in self.db.scalars(
                select(RegistroClima).where(RegistroClima.municipio_id == municipio_id,
                                            RegistroClima.fecha.in_(fechas))
            )
        }
        for f in filas:
            r = existentes.get(f["fecha"])
            if r is None:
                self.db.add(RegistroClima(municipio_id=municipio_id, **f))
            else:
                for k, v in f.items():
                    setattr(r, k, v)
        self.db.commit()
        return len(filas)


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

    def semanas(self, municipio_id: int, enfermedad_id: int, pares: list[tuple[int, int]]) -> list[CasoOficial]:
        if not pares:
            return []
        cond = or_(*[and_(CasoOficial.anio == a, CasoOficial.semana_epi == s) for a, s in pares])
        stmt = select(CasoOficial).where(
            CasoOficial.municipio_id == municipio_id, CasoOficial.enfermedad_id == enfermedad_id, cond)
        return list(self.db.scalars(stmt))

