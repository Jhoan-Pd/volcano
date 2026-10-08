"""Repositorio genérico: encapsula el acceso a datos con SQLAlchemy.

Decisión (patrón Repository): los servicios no escriben consultas SQL; piden datos al
repositorio. Así se puede cambiar el motor de BD o probar con SQLite sin tocar la lógica.
"""
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
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
