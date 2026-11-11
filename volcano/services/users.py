"""Authentication and user management."""
from typing import Any

from volcano.models import Municipality, User
from volcano.models.enums import RoleName
from volcano.repositories.domain import RoleRepository, UserRepository
from volcano.schemas.auth import CitizenSignup
from volcano.schemas.user import UserCreate, UserUpdate
from volcano.services.crud import CrudService
from volcano.shared.errors import BusinessRuleError, ConflictError, NotAuthenticatedError, NotFoundError
from volcano.shared.security import create_token, hash_password, verify_password


class AuthService:
    def __init__(self, db):
        self.db = db
        self.users = UserRepository(db)
        self.user_service = UserService(db)

    def authenticate(self, email: str, password: str) -> tuple[User, str]:
        user = self.users.by_email(email)
        # Same message for an unknown e-mail and a wrong password: it does not reveal which accounts exist
        if user is None or not verify_password(password, user.password_hash):
            raise NotAuthenticatedError("Correo o contraseña incorrectos")
        if not user.active:
            raise NotAuthenticatedError("La cuenta está desactivada")
        return user, create_token(user.id, user.role_name, {"name": user.name})

    def register_citizen(self, data: CitizenSignup) -> User:
        payload = UserCreate(name=data.name, email=data.email, password=data.password,
                             municipality_id=data.municipality_id, role=RoleName.CITIZEN)
        return self.user_service.create(payload)


class UserService(CrudService[User]):
    repository_cls = UserRepository
    entity_name = "Usuario"

    def __init__(self, db):
        super().__init__(db)
        self.roles = RoleRepository(db)

    def _role_id(self, role: RoleName | str) -> int:
        r = self.roles.by_name(str(role))
        if r is None:
            raise BusinessRuleError(f"El rol {role} no existe (¿se ejecutó el seed?)")
        return r.id

    def _prepare(self, data: dict[str, Any], current: User | None = None) -> dict[str, Any]:
        if data.get("email"):
            data["email"] = data["email"].lower()
            other = self.repo.by_email(data["email"])
            if other and (current is None or other.id != current.id):
                raise ConflictError("Ya existe un usuario con ese correo")
        if data.get("municipality_id") is not None and self.db.get(Municipality, data["municipality_id"]) is None:
            raise NotFoundError(f"Municipio {data['municipality_id']} no existe")
        if "role" in data:
            role = data.pop("role")
            if role is not None:
                data["role_id"] = self._role_id(role)
        if "password" in data:
            password = data.pop("password")
            if password:
                data["password_hash"] = hash_password(password)
        return data

    def create(self, payload: UserCreate, **_: Any) -> User:
        return self.repo.create(self._prepare(payload.model_dump()))

    def update(self, id_: int, payload: UserUpdate, actor: User | None = None) -> User:
        obj = self.get(id_)
        data = payload.model_dump(exclude_unset=True)
        if actor is not None and actor.id == obj.id:
            if data.get("active") is False:
                raise BusinessRuleError("No puedes desactivar tu propia cuenta")
            if data.get("role") not in (None, RoleName.ADMIN):
                raise BusinessRuleError("No puedes quitarte el rol ADMIN a ti mismo")
        return self.repo.update(obj, self._prepare(data, obj))

    def delete(self, id_: int, actor: User | None = None) -> None:
        if actor is not None and actor.id == id_:
            raise BusinessRuleError("No puedes eliminar tu propia cuenta")
        super().delete(id_)
