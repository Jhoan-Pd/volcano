"""Generic repository: wraps data access with SQLAlchemy.

Services never write SQL; they ask a repository. The database engine can change (or tests can
use SQLite) without touching business logic.
"""
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from volcano.db.base import Base


class BaseRepository[ModelT: Base]:
    model: type[ModelT]

    def __init__(self, db: Session):
        self.db = db

    def get(self, id_: int) -> ModelT | None:
        return self.db.get(self.model, id_)

    def get_by(self, **filters: Any) -> ModelT | None:
        return self.db.scalars(select(self.model).filter_by(**filters).limit(1)).first()

    def list_page(self, offset: int = 0, limit: int = 100, order_by: Any = None, **filters: Any) -> list[ModelT]:
        stmt = select(self.model).filter_by(**{k: v for k, v in filters.items() if v is not None})
        stmt = stmt.order_by(order_by if order_by is not None else self.model.id)
        return list(self.db.scalars(stmt.offset(offset).limit(limit)).unique())

    def count(self, **filters: Any) -> int:
        stmt = select(func.count()).select_from(self.model).filter_by(
            **{k: v for k, v in filters.items() if v is not None}
        )
        return self.db.scalar(stmt) or 0

    def create(self, data: dict[str, Any]) -> ModelT:
        obj = self.model(**data)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update(self, obj: ModelT, data: dict[str, Any]) -> ModelT:
        for field, value in data.items():
            setattr(obj, field, value)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete(self, obj: ModelT) -> None:
        self.db.delete(obj)
        self.db.commit()

    def upsert(self, rows: list[dict[str, Any]], key: tuple[str, ...], scope: list[Any] | None = None,
               ) -> tuple[int, int]:
        """Insert or update by a natural key (e.g. municipality + date). Returns (inserted, updated).

        One query loads the existing rows inside `scope` (SQL conditions that narrow the search)
        and indexes them by key, so each row resolves in O(1) instead of one query per row. Works on
        SQLite and PostgreSQL alike (no ON CONFLICT, whose syntax differs between engines).
        """
        if not rows:
            return 0, 0
        stmt = select(self.model)
        if scope:
            stmt = stmt.where(*scope)
        existing = {tuple(getattr(o, c) for c in key): o for o in self.db.scalars(stmt)}
        inserted = updated = 0
        for row in rows:
            k = tuple(row[c] for c in key)
            obj = existing.get(k)
            if obj is None:
                existing[k] = obj = self.model(**row)
                self.db.add(obj)
                inserted += 1
            else:
                for field, value in row.items():
                    setattr(obj, field, value)
                updated += 1
        self.db.commit()
        return inserted, updated
