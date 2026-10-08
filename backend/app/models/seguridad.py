from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Rol(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(200))

    usuarios: Mapped[list["Usuario"]] = relationship(back_populates="rol")


class Usuario(TimestampMixin, Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(100), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rol_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False)
    municipio_id: Mapped[int | None] = mapped_column(ForeignKey("municipios.id", ondelete="SET NULL"))

    rol: Mapped[Rol] = relationship(back_populates="usuarios", lazy="joined")
    municipio: Mapped["Municipio | None"] = relationship(lazy="joined")  # noqa: F821

    @property
    def rol_nombre(self) -> str:
        return self.rol.nombre if self.rol else ""
