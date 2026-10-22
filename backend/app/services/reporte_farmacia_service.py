"""Reportes semanales de farmacias: registro, historial, edición y eliminación.

Reglas de negocio:
- Un usuario FARMACIA solo reporta por la farmacia que tiene asignada; el ADMIN por cualquiera.
- Solo se reportan semanas epidemiológicas ya terminadas (no la semana en curso ni futuras).
- La farmacia puede crear o corregir reportes de las últimas VENTANA_EDICION semanas; los
  más antiguos solo los cambia el ADMIN (así el histórico del modelo no se altera sin control).
- Una semana se reporta una sola vez (POST); para corregirla se usa PUT.
"""
from datetime import date, timedelta

from sqlalchemy import delete, select

from app.core.epi import desplazar, etiqueta, inicio_semana, ultima_semana_completa
from app.core.errors import ConflictoError, NoEncontradoError, PermisoDenegadoError, ReglaNegocioError
from app.models import Farmacia, ReporteFarmacia, Usuario
from app.models.enums import CategoriaProducto, RolNombre
from app.schemas.farmacia import (
    ItemReporte,
    ItemReporteOut,
    MiFarmacia,
    ReporteSemanalIn,
    ReporteSemanalOut,
    SemanaReportable,
)

VENTANA_EDICION = 8


class ReporteFarmaciaService:
    def __init__(self, db, actor: Usuario):
        self.db = db
        self.actor = actor
        self.es_admin = actor.rol_nombre == RolNombre.ADMIN

    # ── farmacia del usuario ──────────────────────────────────────────────────
    def farmacia(self, farmacia_id: int | None = None) -> Farmacia:
        if self.es_admin:
            if farmacia_id is None:
                raise ReglaNegocioError("Como ADMIN debes indicar farmacia_id")
            f = self.db.get(Farmacia, farmacia_id)
            if f is None:
                raise NoEncontradoError(f"Farmacia {farmacia_id} no existe")
            return f
        f = self.db.scalar(select(Farmacia).where(Farmacia.usuario_id == self.actor.id))
        if f is None:
            raise NoEncontradoError("Tu usuario no está asignado a ninguna farmacia. "
                                    "Pide al administrador que te asigne.")
        if farmacia_id is not None and farmacia_id != f.id:
            raise PermisoDenegadoError("Solo puedes reportar por tu propia farmacia")
        return f

    @staticmethod
    def semanas_reportables(hoy: date | None = None) -> list[tuple[int, int]]:
        ultima = ultima_semana_completa(hoy)
        return [desplazar(*ultima, -k) for k in range(VENTANA_EDICION)]

    def _validar_semana(self, anio: int, semana: int) -> None:
        if (anio, semana) > ultima_semana_completa():
            raise ReglaNegocioError("Solo se pueden reportar semanas epidemiológicas ya terminadas")
        if not self.es_admin and (anio, semana) not in self.semanas_reportables():
            raise ReglaNegocioError(
                f"Solo puedes registrar o corregir las últimas {VENTANA_EDICION} semanas. "
                "Para semanas anteriores contacta al administrador.")

    # ── lectura ───────────────────────────────────────────────────────────────
    def _filas_semana(self, farmacia_id: int, anio: int, semana: int) -> list[ReporteFarmacia]:
        return list(self.db.scalars(select(ReporteFarmacia).where(
            ReporteFarmacia.farmacia_id == farmacia_id, ReporteFarmacia.anio == anio,
            ReporteFarmacia.semana_epi == semana).order_by(ReporteFarmacia.categoria)))

    def _salida(self, f: Farmacia, anio: int, semana: int, filas: list[ReporteFarmacia]) -> ReporteSemanalOut:
        ini = inicio_semana(anio, semana)
        orden = list(CategoriaProducto.__members__)
        filas = sorted(filas, key=lambda r: orden.index(r.categoria) if r.categoria in orden else 99)
        autor_id = next((r.reportado_por_id for r in filas if r.reportado_por_id), None)
        autor = self.db.get(Usuario, autor_id) if autor_id else None
        return ReporteSemanalOut(
            farmacia_id=f.id, farmacia=f.nombre, anio=anio, semana_epi=semana, etiqueta=etiqueta(anio, semana),
            fecha_inicio=ini, fecha_fin=ini + timedelta(days=6),
            items=[ItemReporteOut(categoria=r.categoria, unidades=r.unidades) for r in filas],
            total_unidades=sum(r.unidades for r in filas), es_simulado=any(r.es_simulado for r in filas),
            actualizado_en=max((r.actualizado_en for r in filas), default=None),
            reportado_por=autor.nombre if autor else None,
            editable=self.es_admin or (anio, semana) in self.semanas_reportables(),
        )

    def mi_farmacia(self, farmacia_id: int | None = None) -> MiFarmacia:
        f = self.farmacia(farmacia_id)
        reportadas = set(self.db.execute(
            select(ReporteFarmacia.anio, ReporteFarmacia.semana_epi).where(ReporteFarmacia.farmacia_id == f.id)
            .distinct()).all())
        semanas = []
        for a, s in self.semanas_reportables():
            ini = inicio_semana(a, s)
            semanas.append(SemanaReportable(anio=a, semana_epi=s, etiqueta=etiqueta(a, s), fecha_inicio=ini,
                                            fecha_fin=ini + timedelta(days=6), reportada=(a, s) in reportadas))
        return MiFarmacia(id=f.id, nombre=f.nombre, nit=f.nit, direccion=f.direccion, municipio_id=f.municipio_id,
                          municipio=f.municipio.nombre if f.municipio else "", activa=f.activa,
                          semanas_reportables=semanas, categorias=list(CategoriaProducto.__members__))

    def historial(self, farmacia_id: int | None = None, semanas: int = 26) -> list[ReporteSemanalOut]:
        f = self.farmacia(farmacia_id)
        desde = desplazar(*ultima_semana_completa(), -(semanas - 1))
        filas = self.db.scalars(select(ReporteFarmacia).where(ReporteFarmacia.farmacia_id == f.id)).all()
        por_semana: dict[tuple[int, int], list[ReporteFarmacia]] = {}
        for r in filas:
            if (r.anio, r.semana_epi) >= desde:
                por_semana.setdefault((r.anio, r.semana_epi), []).append(r)
        return [self._salida(f, a, s, por_semana[(a, s)]) for a, s in sorted(por_semana, reverse=True)]

    def obtener(self, anio: int, semana: int, farmacia_id: int | None = None) -> ReporteSemanalOut:
        f = self.farmacia(farmacia_id)
        filas = self._filas_semana(f.id, anio, semana)
        if not filas:
            raise NoEncontradoError(f"No hay reporte de la semana {etiqueta(anio, semana)}")
        return self._salida(f, anio, semana, filas)

    # ── escritura ─────────────────────────────────────────────────────────────
    def _guardar_items(self, f: Farmacia, anio: int, semana: int, items: list[ItemReporte]) -> None:
        self.db.execute(delete(ReporteFarmacia).where(
            ReporteFarmacia.farmacia_id == f.id, ReporteFarmacia.anio == anio, ReporteFarmacia.semana_epi == semana))
        self.db.add_all([ReporteFarmacia(farmacia_id=f.id, anio=anio, semana_epi=semana, categoria=i.categoria.value,
                                         unidades=i.unidades, reportado_por_id=self.actor.id, es_simulado=False)
                         for i in items])
        self.db.commit()

    def crear(self, entrada: ReporteSemanalIn) -> ReporteSemanalOut:
        f = self.farmacia(entrada.farmacia_id)
        if not f.activa:
            raise ReglaNegocioError("La farmacia está inactiva y no puede reportar")
        self._validar_semana(entrada.anio, entrada.semana_epi)
        if self._filas_semana(f.id, entrada.anio, entrada.semana_epi):
            raise ConflictoError(f"Ya existe el reporte de la semana {etiqueta(entrada.anio, entrada.semana_epi)}. "
                                 "Usa la opción Editar para corregirlo.")
        self._guardar_items(f, entrada.anio, entrada.semana_epi, entrada.items)
        return self.obtener(entrada.anio, entrada.semana_epi, f.id if self.es_admin else None)

    def actualizar(self, anio: int, semana: int, items: list[ItemReporte],
                   farmacia_id: int | None = None) -> ReporteSemanalOut:
        f = self.farmacia(farmacia_id)
        self._validar_semana(anio, semana)
        if not self._filas_semana(f.id, anio, semana):
            raise NoEncontradoError(f"No hay reporte de la semana {etiqueta(anio, semana)} para editar")
        self._guardar_items(f, anio, semana, items)
        return self.obtener(anio, semana, f.id if self.es_admin else None)

    def eliminar(self, anio: int, semana: int, farmacia_id: int | None = None) -> None:
        f = self.farmacia(farmacia_id)
        self._validar_semana(anio, semana)
        if not self._filas_semana(f.id, anio, semana):
            raise NoEncontradoError(f"No hay reporte de la semana {etiqueta(anio, semana)}")
        self.db.execute(delete(ReporteFarmacia).where(
            ReporteFarmacia.farmacia_id == f.id, ReporteFarmacia.anio == anio, ReporteFarmacia.semana_epi == semana))
        self.db.commit()
