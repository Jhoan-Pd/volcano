"""Generic CRUD service: the common rules (existence, uniqueness, pagination) in one place.

Subclasses override `validate()` for entity-specific rules.
"""
from typing import Any

from pydantic import BaseModel

from volcano.repositories.base import BaseRepository
from volcano.shared.errors import ConflictError, NotFoundError


class CrudService[ModelT]:
    repository_cls: type[BaseRepository]
    entity_name: str = "Registro"  # Spanish: it appears in error messages shown to the user
    #: UNIQUE columns checked before inserting (a clear message instead of a 500)
    unique_fields: tuple[str, ...] = ()

    def __init__(self, db):
        self.db = db
        self.repo = self.repository_cls(db)

    def get(self, id_: int) -> ModelT:
        obj = self.repo.get(id_)
        if obj is None:
            raise NotFoundError(f"{self.entity_name} {id_} no existe")
        return obj

    def order_by(self) -> Any:
        """Listing order (by default, ascending id)."""
        return None

    def list_page(self, offset: int = 0, limit: int = 100, **filters: Any) -> tuple[list[ModelT], int]:
        items = self.repo.list_page(offset=offset, limit=limit, order_by=self.order_by(), **filters)
        return items, self.repo.count(**filters)

    def _check_unique(self, data: dict[str, Any], current: ModelT | None = None) -> None:
        for field in self.unique_fields:
            if field in data and data[field] is not None:
                other = self.repo.get_by(**{field: data[field]})
                if other is not None and (current is None or other.id != current.id):
                    raise ConflictError(f"Ya existe un(a) {self.entity_name.lower()} con {field}={data[field]}")

    def validate(self, data: dict[str, Any], current: ModelT | None = None) -> dict[str, Any]:
        """Hook for business rules; returns the (possibly transformed) data."""
        return data

    def create(self, payload: BaseModel, **extra: Any) -> ModelT:
        data = {**payload.model_dump(), **extra}
        self._check_unique(data)
        data = self.validate(data)
        return self.repo.create(data)

    def update(self, id_: int, payload: BaseModel) -> ModelT:
        obj = self.get(id_)
        data = payload.model_dump(exclude_unset=True)
        self._check_unique(data, obj)
        data = self.validate(data, obj)
        return self.repo.update(obj, data)

    def before_delete(self, obj: ModelT) -> None:
        """Hook: raise an error when the row cannot be deleted."""

    def delete(self, id_: int) -> None:
        obj = self.get(id_)
        self.before_delete(obj)
        self.repo.delete(obj)
