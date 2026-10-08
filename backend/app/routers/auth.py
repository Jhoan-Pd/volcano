from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.deps import get_usuario_actual
from app.db.session import get_db
from app.models import Usuario
from app.schemas.auth import RegistroCiudadano, Token
from app.schemas.usuario import UsuarioOut
from app.services.usuario_service import AuthService

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/login", response_model=Token, summary="Iniciar sesión (devuelve JWT)")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Formulario OAuth2 estándar: campos `username` (correo) y `password`.
    Es compatible con el botón **Authorize** de Swagger."""
    usuario, token = AuthService(db).autenticar(form.username, form.password)
    return Token(access_token=token, usuario=UsuarioOut.desde(usuario))


@router.post("/registro", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED,
             summary="Registro público de ciudadanos")
def registro(datos: RegistroCiudadano, db: Session = Depends(get_db)):
    return UsuarioOut.desde(AuthService(db).registrar_ciudadano(datos))


@router.get("/me", response_model=UsuarioOut, summary="Usuario autenticado")
def me(usuario: Usuario = Depends(get_usuario_actual)):
    return UsuarioOut.desde(usuario)
