"""Repositorio genérico: encapsula el acceso a datos con SQLAlchemy.

Decisión (patrón Repository): los servicios no escriben consultas SQL; piden datos al
repositorio. Así se puede cambiar el motor de BD o probar con SQLite sin tocar la lógica.
"""
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import Base


class BaseRepository[ModelT: Base]:
    model: type[ModelT]

    def __init__(self, db: Session):
        self.db = db

    def obtener(self, id_: int) -> ModelT | None:
        return self.db.get(self.model, id_)

    def obtener_por(self, **filtros: Any) -> ModelT | None:
        return self.db.scalars(select(self.model).filter_by(**filtros).limit(1)).first()

    def listar(self, offset: int = 0, limit: int = 100, orden: Any = None, **filtros: Any) -> list[ModelT]:
        stmt = select(self.model).filter_by(**{k: v for k, v in filtros.items() if v is not None})
        stmt = stmt.order_by(orden if orden is not None else self.model.id)
        return list(self.db.scalars(stmt.offset(offset).limit(limit)).unique())

    def contar(self, **filtros: Any) -> int:
        stmt = select(func.count()).select_from(self.model).filter_by(
            **{k: v for k, v in filtros.items() if v is not None}
        )
        return self.db.scalar(stmt) or 0

    def crear(self, datos: dict[str, Any]) -> ModelT:
        obj = self.model(**datos)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def actualizar(self, obj: ModelT, datos: dict[str, Any]) -> ModelT:
        for campo, valor in datos.items():
            setattr(obj, campo, valor)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def eliminar(self, obj: ModelT) -> None:
        self.db.delete(obj)
        self.db.commit()

    def upsert(self, filas: list[dict[str, Any]], clave: tuple[str, ...], alcance: list[Any] | None = None,
               ) -> tuple[int, int]:
        """Inserta o actualiza por una clave natural (p. ej. municipio + fecha). Devuelve (insertadas, actualizadas).

        Una sola consulta trae los registros existentes dentro de `alcance` (condiciones SQL que
        acotan la búsqueda) y se indexan en un diccionario por clave: cada fila se resuelve en O(1)
        en vez de hacer una consulta por fila. Portable entre SQLite y PostgreSQL (no usa
        ON CONFLICT, que cambia de sintaxis según el motor).
        """
        if not filas:
            return 0, 0
        stmt = select(self.model)
        if alcance:
            stmt = stmt.where(*alcance)
        existentes = {tuple(getattr(o, c) for c in clave): o for o in self.db.scalars(stmt)}
        insertadas = actualizadas = 0
        for fila in filas:
            k = tuple(fila[c] for c in clave)
            obj = existentes.get(k)
            if obj is None:
                existentes[k] = obj = self.model(**fila)
                self.db.add(obj)
                insertadas += 1
            else:
                for campo, valor in fila.items():
                    setattr(obj, campo, valor)
                actualizadas += 1
        self.db.commit()
        return insertadas, actualizadas
