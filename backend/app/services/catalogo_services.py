"""Servicios CRUD de municipios, enfermedades, farmacias y eventos volcánicos."""
from typing import Any

from sqlalchemy import func, select

from app.core.errors import ConflictoError, NoEncontradoError, ReglaNegocioError
from app.models import CasoOficial, EventoVolcanico, Farmacia, Municipio, Usuario
from app.models.enums import RolNombre
from app.repositories.repos import (
    EnfermedadRepository, EventoVolcanicoRepository, FarmaciaRepository, MunicipioRepository,
)
from app.schemas.catalogos import EventoVolcanicoBase
from app.services.crud_service import CrudService


def _existe(db, modelo, id_: int | None, nombre: str) -> None:
    if id_ is not None and db.get(modelo, id_) is None:
        raise NoEncontradoError(f"{nombre} {id_} no existe")


class MunicipioService(CrudService[Municipio]):
    repo_cls = MunicipioRepository
    nombre_entidad = "Municipio"
    campos_unicos = ("codigo_divipola",)

    def antes_de_eliminar(self, obj) -> None:
        casos = self.db.scalar(select(func.count()).where(CasoOficial.municipio_id == obj.id))
        farmacias = self.db.scalar(select(func.count()).where(Farmacia.municipio_id == obj.id))
        if casos or farmacias:
            raise ConflictoError(
                f"El municipio tiene {casos} registros de casos y {farmacias} farmacias. "
                "Desactívalo (activo=false) en lugar de eliminarlo para conservar el histórico."
            )


class EnfermedadService(CrudService):
    repo_cls = EnfermedadRepository
    nombre_entidad = "Enfermedad"
    campos_unicos = ("codigo",)

    def validar(self, datos: dict[str, Any], actual=None) -> dict[str, Any]:
        if actual is not None:  # en edición parcial se validan los umbrales resultantes
            a = datos.get("umbral_amarillo_pct", actual.umbral_amarillo_pct)
            n = datos.get("umbral_naranja_pct", actual.umbral_naranja_pct)
            r = datos.get("umbral_rojo_pct", actual.umbral_rojo_pct)
            if not (a < n < r):
                raise ReglaNegocioError("Los umbrales deben cumplir amarillo < naranja < rojo")
        return datos

    def antes_de_eliminar(self, obj) -> None:
        casos = self.db.scalar(select(func.count()).where(CasoOficial.enfermedad_id == obj.id))
        if casos:
            raise ConflictoError(
                f"La enfermedad tiene {casos} registros de casos. Desactívala en lugar de eliminarla."
            )


class FarmaciaService(CrudService):
    repo_cls = FarmaciaRepository
    nombre_entidad = "Farmacia"
    campos_unicos = ("nit", "usuario_id")

    def validar(self, datos: dict[str, Any], actual=None) -> dict[str, Any]:
        _existe(self.db, Municipio, datos.get("municipio_id"), "Municipio")
        uid = datos.get("usuario_id")
        if uid is not None:
            usuario = self.db.get(Usuario, uid)
            if usuario is None:
                raise NoEncontradoError(f"Usuario {uid} no existe")
            if usuario.rol_nombre != RolNombre.FARMACIA:
                raise ReglaNegocioError("El usuario asignado a una farmacia debe tener rol FARMACIA")
        return datos


class EventoVolcanicoService(CrudService):
    repo_cls = EventoVolcanicoRepository
    nombre_entidad = "Evento volcánico"

    def orden(self):
        return EventoVolcanico.fecha_inicio.desc()

    def validar(self, datos: dict[str, Any], actual=None) -> dict[str, Any]:
        _existe(self.db, Municipio, datos.get("municipio_id"), "Municipio")
        if actual is not None:
            # Se valida el objeto resultante completo (reglas de ceniza y fechas)
            campos = EventoVolcanicoBase.model_fields.keys()
            fusion = {c: getattr(actual, c) for c in campos} | datos
            try:
                EventoVolcanicoBase.model_validate(fusion)
            except ValueError as exc:
                raise ReglaNegocioError(str(exc).split("\n")[-1].strip()) from None
        for clave in ("tipo", "nivel_actividad"):
            if clave in datos and datos[clave] is not None:
                datos[clave] = str(datos[clave].value if hasattr(datos[clave], "value") else datos[clave])
        return datos
