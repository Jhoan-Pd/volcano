from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import solo_admin
from app.db.session import get_db
from app.models import Usuario
from app.schemas.comun import Pagina
from app.schemas.usuario import UsuarioCreate, UsuarioOut, UsuarioUpdate
from app.services.usuario_service import UsuarioService

router = APIRouter(prefix="/usuarios", tags=["Usuarios"], dependencies=[Depends(solo_admin)])


@router.get("", response_model=Pagina[UsuarioOut], summary="Listar usuarios — solo ADMIN")
def listar(offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    items, total = UsuarioService(db).listar(offset=offset, limit=limit)
    return Pagina(items=[UsuarioOut.desde(u) for u in items], total=total, offset=offset, limit=limit)


@router.get("/{id_}", response_model=UsuarioOut)
def obtener(id_: int, db: Session = Depends(get_db)):
    return UsuarioOut.desde(UsuarioService(db).obtener(id_))


@router.post("", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def crear(entrada: UsuarioCreate, db: Session = Depends(get_db)):
    return UsuarioOut.desde(UsuarioService(db).crear(entrada))


@router.patch("/{id_}", response_model=UsuarioOut)
def actualizar(id_: int, entrada: UsuarioUpdate, db: Session = Depends(get_db), admin: Usuario = Depends(solo_admin)):
    return UsuarioOut.desde(UsuarioService(db).actualizar(id_, entrada, actor=admin))


@router.delete("/{id_}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(id_: int, db: Session = Depends(get_db), admin: Usuario = Depends(solo_admin)):
    UsuarioService(db).eliminar(id_, actor=admin)
