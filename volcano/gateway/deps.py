"""FastAPI dependencies: database session, authenticated user and role checks."""
import secrets
from collections.abc import Callable

import jwt
from fastapi import Depends, Header
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from volcano.db.session import get_db
from volcano.models import User
from volcano.models.enums import RoleName
from volcano.shared.config import settings
from volcano.shared.errors import NotAuthenticatedError, PermissionDeniedError
from volcano.shared.security import decode_token

oauth2 = OAuth2PasswordBearer(tokenUrl=f"{settings.API_PREFIX}/auth/login", auto_error=False)


def current_user(token: str | None = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    if not token:
        raise NotAuthenticatedError("Debes iniciar sesión")
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise NotAuthenticatedError("La sesión expiró, inicia sesión de nuevo") from None
    except jwt.PyJWTError:
        raise NotAuthenticatedError("Token inválido") from None
    user = db.get(User, int(payload["sub"]))
    if not user or not user.active:
        raise NotAuthenticatedError("Usuario inexistente o inactivo")
    return user


def require_roles(*roles: RoleName) -> Callable[..., User]:
    """Usage: `Depends(require_roles(RoleName.ADMIN))`."""
    allowed = {r.value for r in roles}

    def _dependency(user: User = Depends(current_user)) -> User:
        if user.role_name not in allowed:
            raise PermissionDeniedError(f"Se requiere el rol: {', '.join(sorted(allowed))}")
        return user

    return _dependency


admin_only = require_roles(RoleName.ADMIN)
pharmacy_or_admin = require_roles(RoleName.PHARMACY, RoleName.ADMIN)


def verify_cron_secret(x_cron_secret: str | None = Header(default=None)) -> None:
    """Protects the endpoints GitHub Actions calls with a shared secret."""
    # compare_digest compares in constant time (does not leak the secret through response times)
    if not x_cron_secret or not secrets.compare_digest(x_cron_secret, settings.CRON_SECRET):
        raise NotAuthenticatedError("Secreto de cron inválido")
