import uuid
from datetime import datetime
from ipaddress import IPv4Address, IPv6Address
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class AuditLog(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "audit_logs"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    entity_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        nullable=True,
        index=True,
    )

    ip_address: Mapped[str | IPv4Address | IPv6Address | None] = mapped_column(
        INET,
        nullable=True,
    )

    user_agent: Mapped[str | None] = mapped_column(String(512))

    details: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    user: Mapped["User | None"] = relationship(
        back_populates="audit_logs",
    )

    def __repr__(self):
        return (
            f"<AuditLog("
            f"id={self.id}, "
            f"action={self.action}, "
            f"entity_type={self.entity_type})>"
        )
