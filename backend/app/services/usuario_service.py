"""Autenticación y gestión de usuarios."""
from typing import Any

from app.core.errors import ConflictoError, NoAutenticadoError, NoEncontradoError, ReglaNegocioError
from app.core.security import crear_token, hash_password, verify_password
from app.models import Municipio, Usuario
from app.models.enums import RolNombre
from app.repositories.repos import RolRepository, UsuarioRepository
from app.schemas.auth import RegistroCiudadano
from app.schemas.usuario import UsuarioCreate, UsuarioUpdate
from app.services.crud_service import CrudService


class AuthService:
    def __init__(self, db):
        self.db = db
        self.usuarios = UsuarioRepository(db)
        self.usuario_service = UsuarioService(db)

    def autenticar(self, email: str, password: str) -> tuple[Usuario, str]:
        usuario = self.usuarios.por_email(email)
        # Mismo mensaje para email inexistente y clave errada: no revela qué cuentas existen
        if usuario is None or not verify_password(password, usuario.password_hash):
            raise NoAutenticadoError("Correo o contraseña incorrectos")
        if not usuario.activo:
            raise NoAutenticadoError("La cuenta está desactivada")
        return usuario, crear_token(usuario.id, usuario.rol_nombre, {"nombre": usuario.nombre})

    def registrar_ciudadano(self, datos: RegistroCiudadano) -> Usuario:
        entrada = UsuarioCreate(nombre=datos.nombre, email=datos.email, password=datos.password,
                                municipio_id=datos.municipio_id, rol=RolNombre.CIUDADANO)
        return self.usuario_service.crear(entrada)


class UsuarioService(CrudService[Usuario]):
    repo_cls = UsuarioRepository
    nombre_entidad = "Usuario"

    def __init__(self, db):
        super().__init__(db)
        self.roles = RolRepository(db)

    def _rol_id(self, rol: RolNombre | str) -> int:
        r = self.roles.por_nombre(str(rol))
        if r is None:
            raise ReglaNegocioError(f"Rol {rol} no existe (¿ejecutaste el seed?)")
        return r.id

    def _preparar(self, datos: dict[str, Any], actual: Usuario | None = None) -> dict[str, Any]:
        if datos.get("email"):
            datos["email"] = datos["email"].lower()
            otro = self.repo.por_email(datos["email"])
            if otro and (actual is None or otro.id != actual.id):
                raise ConflictoError("Ya existe un usuario con ese correo")
        if datos.get("municipio_id") is not None and self.db.get(Municipio, datos["municipio_id"]) is None:
            raise NoEncontradoError(f"Municipio {datos['municipio_id']} no existe")
        if "rol" in datos:
            rol = datos.pop("rol")
            if rol is not None:
                datos["rol_id"] = self._rol_id(rol)
        if "password" in datos:
            pwd = datos.pop("password")
            if pwd:
                datos["password_hash"] = hash_password(pwd)
        return datos

    def crear(self, entrada: UsuarioCreate, **_: Any) -> Usuario:
        return self.repo.crear(self._preparar(entrada.model_dump()))

    def actualizar(self, id_: int, entrada: UsuarioUpdate, actor: Usuario | None = None) -> Usuario:
        obj = self.obtener(id_)
        datos = entrada.model_dump(exclude_unset=True)
        if actor is not None and actor.id == obj.id:
            if datos.get("activo") is False:
                raise ReglaNegocioError("No puedes desactivar tu propia cuenta")
            if datos.get("rol") not in (None, RolNombre.ADMIN):
                raise ReglaNegocioError("No puedes quitarte el rol ADMIN a ti mismo")
        return self.repo.actualizar(obj, self._preparar(datos, obj))

    def eliminar(self, id_: int, actor: Usuario | None = None) -> None:
        if actor is not None and actor.id == id_:
            raise ReglaNegocioError("No puedes eliminar tu propia cuenta")
        super().eliminar(id_)
