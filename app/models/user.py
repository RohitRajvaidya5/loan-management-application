import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.application_note import ApplicationNote
    from app.models.audit_log import AuditLog
    from app.models.loan_application import LoanApplication
    from app.models.role import Role


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    token_version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    full_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    role_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("roles.id"),
        nullable=False,
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    role: Mapped["Role"] = relationship(
        back_populates="users",
        lazy="joined",
    )

    assigned_applications: Mapped[list["LoanApplication"]] = relationship(
        back_populates="assigned_user",
        foreign_keys="LoanApplication.assigned_to",
    )

    audit_logs: Mapped[list["AuditLog"]] = relationship(
        back_populates="user",
    )

    application_notes: Mapped[list["ApplicationNote"]] = relationship(
        back_populates="author",
    )

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email})>"
