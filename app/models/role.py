from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)

if TYPE_CHECKING:
    from app.models.permission import Permission
    from app.models.user import User


class Role(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )

    description: Mapped[str] = mapped_column(String(255), nullable=True)

    permissions: Mapped[list["Permission"]] = relationship(
        secondary="role_permissions",
        back_populates="roles",
        lazy="selectin",
    )

    users: Mapped[list["User"]] = relationship(back_populates="role")

    def __repr__(self) -> str:
        return f"<Role(id={self.id}, name={self.name})>"
