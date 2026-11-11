from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from volcano.models.enums import RoleName
from volcano.schemas.common import ORMModel


def validate_password(v: str | None) -> str | None:
    if v is None:
        return v
    if not any(c.isdigit() for c in v) or not any(c.isalpha() for c in v):
        raise ValueError("La contraseña debe tener letras y números")
    return v


class UserBase(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    email: EmailStr
    role: RoleName = RoleName.CITIZEN
    municipality_id: int | None = None
    active: bool = True


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=72)
    _v = field_validator("password")(validate_password)


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=120)
    email: EmailStr | None = None
    role: RoleName | None = None
    municipality_id: int | None = None
    active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=72)
    _v = field_validator("password")(validate_password)


class UserOut(ORMModel):
    id: int
    name: str
    email: str
    role: str
    municipality_id: int | None
    active: bool
    created_at: datetime

    @classmethod
    def from_user(cls, u) -> "UserOut":
        return cls(id=u.id, name=u.name, email=u.email, role=u.role_name,
                   municipality_id=u.municipality_id, active=u.active, created_at=u.created_at)
