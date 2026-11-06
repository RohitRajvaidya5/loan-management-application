from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)

if TYPE_CHECKING:
    from app.models.role import Role


class Permission(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "permissions"

    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )

    description: Mapped[str] = mapped_column(String(255), nullable=True)

    roles: Mapped[list["Role"]] = relationship(
        secondary="role_permissions",
        back_populates="permissions",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Permission(id={self.id}, name={self.name})>"
