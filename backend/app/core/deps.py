"""Dependencias de FastAPI: sesión de BD, usuario autenticado y control de roles."""
import secrets
from collections.abc import Callable

import jwt
from fastapi import Depends, Header
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import NoAutenticadoError, PermisoDenegadoError
from app.core.security import decodificar_token
from app.db.session import get_db
from app.models import Usuario
from app.models.enums import RolNombre

oauth2 = OAuth2PasswordBearer(tokenUrl=f"{settings.API_PREFIX}/auth/login", auto_error=False)


def get_usuario_actual(token: str | None = Depends(oauth2), db: Session = Depends(get_db)) -> Usuario:
    if not token:
        raise NoAutenticadoError("Debes iniciar sesión")
    try:
        payload = decodificar_token(token)
    except jwt.ExpiredSignatureError:
        raise NoAutenticadoError("La sesión expiró, inicia sesión de nuevo") from None
    except jwt.PyJWTError:
        raise NoAutenticadoError("Token inválido") from None
    usuario = db.get(Usuario, int(payload["sub"]))
    if not usuario or not usuario.activo:
        raise NoAutenticadoError("Usuario inexistente o inactivo")
    return usuario


def requiere_roles(*roles: RolNombre) -> Callable[..., Usuario]:
    """Uso: `Depends(requiere_roles(RolNombre.ADMIN))`."""
    permitidos = {r.value for r in roles}

    def _dep(usuario: Usuario = Depends(get_usuario_actual)) -> Usuario:
        if usuario.rol_nombre not in permitidos:
            raise PermisoDenegadoError(f"Se requiere rol: {', '.join(sorted(permitidos))}")
        return usuario

    return _dep


solo_admin = requiere_roles(RolNombre.ADMIN)


def verificar_cron(x_cron_secret: str | None = Header(default=None)) -> None:
    """Protege los endpoints que llama GitHub Actions con un secreto compartido."""
    # compare_digest compara en tiempo constante (no filtra el secreto por tiempos de respuesta)
    if not x_cron_secret or not secrets.compare_digest(x_cron_secret, settings.CRON_SECRET):
        raise NoAutenticadoError("Secreto de cron inválido")
