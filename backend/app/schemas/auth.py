from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.usuario import UsuarioOut, _validar_password


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioOut


class RegistroCiudadano(BaseModel):
    nombre: str = Field(min_length=3, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72, description="Mínimo 8 caracteres")
    municipio_id: int | None = None

    _v = field_validator("password")(_validar_password)
