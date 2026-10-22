"""Hash de contraseñas (bcrypt) y tokens JWT.

Decisión: se usa la librería `bcrypt` directamente (passlib está sin mantenimiento
y choca con bcrypt>=4.1) y `PyJWT` (python-jose tiene CVEs y poco mantenimiento).
"""
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    # bcrypt solo usa los primeros 72 bytes; se trunca explícitamente para evitar errores.
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:72], password_hash.encode("utf-8"))
    except ValueError:
        return False


def crear_token(sub: str | int, rol: str, extra: dict[str, Any] | None = None) -> str:
    ahora = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(sub),
        "rol": rol,
        "iat": ahora,
        "exp": ahora + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decodificar_token(token: str) -> dict[str, Any]:
    """Lanza jwt.PyJWTError si el token es inválido o expiró."""
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
