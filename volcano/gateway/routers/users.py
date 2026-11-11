from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from volcano.db.session import get_db
from volcano.gateway.deps import admin_only
from volcano.models import User
from volcano.schemas.common import Page
from volcano.schemas.user import UserCreate, UserOut, UserUpdate
from volcano.services.users import UserService

router = APIRouter(prefix="/users", tags=["Users"], dependencies=[Depends(admin_only)])


@router.get("", response_model=Page[UserOut], summary="List users — ADMIN only")
def list_users(offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    items, total = UserService(db).list_page(offset=offset, limit=limit)
    return Page(items=[UserOut.from_user(u) for u in items], total=total, offset=offset, limit=limit)


@router.get("/{id_}", response_model=UserOut)
def get_user(id_: int, db: Session = Depends(get_db)):
    return UserOut.from_user(UserService(db).get(id_))


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    return UserOut.from_user(UserService(db).create(payload))


@router.patch("/{id_}", response_model=UserOut)
def update_user(id_: int, payload: UserUpdate, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    return UserOut.from_user(UserService(db).update(id_, payload, actor=admin))


@router.delete("/{id_}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(id_: int, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    UserService(db).delete(id_, actor=admin)
