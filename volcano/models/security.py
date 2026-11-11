from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from volcano.db.base import Base, TimestampMixin


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(200))

    users: Mapped[list["User"]] = relationship(back_populates="role")


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(100), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False)
    municipality_id: Mapped[int | None] = mapped_column(ForeignKey("municipalities.id", ondelete="SET NULL"))

    role: Mapped[Role] = relationship(back_populates="users", lazy="joined")
    municipality: Mapped["Municipality | None"] = relationship(lazy="joined")  # noqa: F821

    @property
    def role_name(self) -> str:
        return self.role.name if self.role else ""
