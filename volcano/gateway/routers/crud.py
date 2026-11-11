"""CRUD router factory.

Municipalities, diseases, pharmacies and volcanic events share the same 5 endpoints (list, get,
create, update, delete). A function generates the router from the service and the schemas instead of
repeating code; each entity still keeps its own rules in its service.
"""
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from volcano.db.session import get_db
from volcano.gateway.deps import admin_only
from volcano.models import User
from volcano.schemas.common import Page
from volcano.services.crud import CrudService


def build_crud_router(  # noqa: PLR0913 - configurable factory: every parameter is keyword-only
    *, prefix: str, tag: str, service: type[CrudService],
    create_schema: type[BaseModel], update_schema: type[BaseModel], out_schema: type[BaseModel],
    public_read: bool = True, filters: tuple[str, ...] = (), author_field: str | None = None,
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[tag])
    read_dependencies: list[Any] = [] if public_read else [Depends(admin_only)]

    @router.get("", response_model=Page[out_schema], dependencies=read_dependencies, summary=f"List {tag.lower()}")
    def list_items(
        offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500),
        municipality_id: int | None = Query(None, description="Filter (when the entity supports it)"),
        db: Session = Depends(get_db),
    ):
        kwargs = {"municipality_id": municipality_id} if "municipality_id" in filters else {}
        items, total = service(db).list_page(offset=offset, limit=limit, **kwargs)
        return Page(items=[out_schema.model_validate(i) for i in items], total=total, offset=offset, limit=limit)

    @router.get("/{id_}", response_model=out_schema, dependencies=read_dependencies, summary=f"Get {tag.lower()} by id")
    def get_item(id_: int, db: Session = Depends(get_db)):
        return service(db).get(id_)

    @router.post("", response_model=out_schema, status_code=status.HTTP_201_CREATED,
                 summary=f"Create ({tag.lower()}) — ADMIN only")
    def create_item(payload: create_schema, db: Session = Depends(get_db),  # type: ignore[valid-type]
                    admin: User = Depends(admin_only)):
        extra = {author_field: admin.id} if author_field else {}
        return service(db).create(payload, **extra)

    @router.patch("/{id_}", response_model=out_schema, summary=f"Update ({tag.lower()}) — ADMIN only")
    def update_item(id_: int, payload: update_schema, db: Session = Depends(get_db),  # type: ignore[valid-type]
                    _: User = Depends(admin_only)):
        return service(db).update(id_, payload)

    @router.delete("/{id_}", status_code=status.HTTP_204_NO_CONTENT, summary=f"Delete ({tag.lower()}) — ADMIN only")
    def delete_item(id_: int, db: Session = Depends(get_db), _: User = Depends(admin_only)):
        service(db).delete(id_)

    return router
