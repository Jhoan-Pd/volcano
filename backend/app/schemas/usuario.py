from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums import RolNombre
from app.schemas.comun import ORMModel


def _validar_password(v: str | None) -> str | None:
    if v is None:
        return v
    if not any(c.isdigit() for c in v) or not any(c.isalpha() for c in v):
        raise ValueError("La contraseña debe tener letras y números")
    return v


class UsuarioBase(BaseModel):
    nombre: str = Field(min_length=3, max_length=120)
    email: EmailStr
    rol: RolNombre = RolNombre.CIUDADANO
    municipio_id: int | None = None
    activo: bool = True


class UsuarioCreate(UsuarioBase):
    password: str = Field(min_length=8, max_length=72)
    _v = field_validator("password")(_validar_password)


class UsuarioUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=3, max_length=120)
    email: EmailStr | None = None
    rol: RolNombre | None = None
    municipio_id: int | None = None
    activo: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=72)
    _v = field_validator("password")(_validar_password)


class UsuarioOut(ORMModel):
    id: int
    nombre: str
    email: str
    rol: str
    municipio_id: int | None
    activo: bool
    creado_en: datetime

    @classmethod
    def desde(cls, u) -> "UsuarioOut":
        return cls(id=u.id, nombre=u.nombre, email=u.email, rol=u.rol_nombre,
                   municipio_id=u.municipio_id, activo=u.activo, creado_en=u.creado_en)
