"""Fábrica de routers CRUD.

Decisión: municipios, enfermedades, farmacias y eventos volcánicos tienen los mismos 5
endpoints (listar, obtener, crear, actualizar, eliminar). En vez de repetir código, una
función genera el router a partir del servicio y los esquemas; cada entidad sigue teniendo
sus reglas propias en su servicio.
"""
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import solo_admin
from app.db.session import get_db
from app.models import Usuario
from app.schemas.comun import Pagina
from app.services.crud_service import CrudService


def crear_router_crud(  # noqa: PLR0913 - fábrica configurable: todos los parámetros son keyword-only
    *, prefijo: str, etiqueta: str, servicio: type[CrudService],
    esquema_crear: type[BaseModel], esquema_actualizar: type[BaseModel], esquema_salida: type[BaseModel],
    lectura_publica: bool = True, filtros: tuple[str, ...] = (), registrar_autor: str | None = None,
) -> APIRouter:
    router = APIRouter(prefix=prefijo, tags=[etiqueta])
    deps_lectura: list[Any] = [] if lectura_publica else [Depends(solo_admin)]

    @router.get("", response_model=Pagina[esquema_salida], dependencies=deps_lectura,
                summary=f"Listar {etiqueta.lower()}")
    def listar(
        offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500),
        municipio_id: int | None = Query(None, description="Filtro (si la entidad lo soporta)"),
        db: Session = Depends(get_db),
    ):
        kwargs = {"municipio_id": municipio_id} if "municipio_id" in filtros else {}
        items, total = servicio(db).listar(offset=offset, limit=limit, **kwargs)
        return Pagina(items=[esquema_salida.model_validate(i) for i in items], total=total, offset=offset, limit=limit)

    @router.get("/{id_}", response_model=esquema_salida, dependencies=deps_lectura,
                summary=f"Obtener {etiqueta.lower()} por id")
    def obtener(id_: int, db: Session = Depends(get_db)):
        return servicio(db).obtener(id_)

    @router.post("", response_model=esquema_salida, status_code=status.HTTP_201_CREATED,
                 summary=f"Crear ({etiqueta.lower()}) — solo ADMIN")
    def crear(entrada: esquema_crear, db: Session = Depends(get_db), admin: Usuario = Depends(solo_admin)):  # type: ignore[valid-type]
        extra = {registrar_autor: admin.id} if registrar_autor else {}
        return servicio(db).crear(entrada, **extra)

    @router.patch("/{id_}", response_model=esquema_salida, summary=f"Actualizar ({etiqueta.lower()}) — solo ADMIN")
    def actualizar(id_: int, entrada: esquema_actualizar, db: Session = Depends(get_db),  # type: ignore[valid-type]
                   _: Usuario = Depends(solo_admin)):
        return servicio(db).actualizar(id_, entrada)

    @router.delete("/{id_}", status_code=status.HTTP_204_NO_CONTENT,
                   summary=f"Eliminar ({etiqueta.lower()}) — solo ADMIN")
    def eliminar(id_: int, db: Session = Depends(get_db), _: Usuario = Depends(solo_admin)):
        servicio(db).eliminar(id_)

    return router
