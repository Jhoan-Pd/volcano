"""Servicio CRUD genérico: concentra las reglas comunes (existencia, unicidad, paginación).

Las subclases sobrescriben `validar()` para reglas específicas de cada entidad.
"""
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from app.core.errors import ConflictoError, NoEncontradoError
from app.repositories.base import BaseRepository

ModelT = TypeVar("ModelT")


class CrudService(Generic[ModelT]):
    repo_cls: type[BaseRepository]
    nombre_entidad: str = "Registro"
    #: campos con restricción UNIQUE que se validan antes de insertar (mensaje claro, no un 500)
    campos_unicos: tuple[str, ...] = ()

    def __init__(self, db):
        self.db = db
        self.repo = self.repo_cls(db)

    def obtener(self, id_: int) -> ModelT:
        obj = self.repo.obtener(id_)
        if obj is None:
            raise NoEncontradoError(f"{self.nombre_entidad} {id_} no existe")
        return obj

    def orden(self) -> Any:
        """Orden del listado (por defecto, id ascendente)."""
        return None

    def listar(self, offset: int = 0, limit: int = 100, **filtros: Any) -> tuple[list[ModelT], int]:
        items = self.repo.listar(offset=offset, limit=limit, orden=self.orden(), **filtros)
        return items, self.repo.contar(**filtros)

    def _validar_unicos(self, datos: dict[str, Any], actual: ModelT | None = None) -> None:
        for campo in self.campos_unicos:
            if campo in datos and datos[campo] is not None:
                otro = self.repo.obtener_por(**{campo: datos[campo]})
                if otro is not None and (actual is None or otro.id != actual.id):
                    raise ConflictoError(f"Ya existe un(a) {self.nombre_entidad.lower()} con {campo}={datos[campo]}")

    def validar(self, datos: dict[str, Any], actual: ModelT | None = None) -> dict[str, Any]:
        """Gancho para reglas de negocio; devuelve los datos (posiblemente transformados)."""
        return datos

    def crear(self, entrada: BaseModel, **extra: Any) -> ModelT:
        datos = {**entrada.model_dump(), **extra}
        self._validar_unicos(datos)
        datos = self.validar(datos)
        return self.repo.crear(datos)

    def actualizar(self, id_: int, entrada: BaseModel) -> ModelT:
        obj = self.obtener(id_)
        datos = entrada.model_dump(exclude_unset=True)
        self._validar_unicos(datos, obj)
        datos = self.validar(datos, obj)
        return self.repo.actualizar(obj, datos)

    def antes_de_eliminar(self, obj: ModelT) -> None:
        """Gancho: lanza un error si el registro no se puede borrar."""

    def eliminar(self, id_: int) -> None:
        obj = self.obtener(id_)
        self.antes_de_eliminar(obj)
        self.repo.eliminar(obj)
