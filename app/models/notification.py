import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, UUIDPrimaryKeyMixin


class Notification(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_due", "status", "available_at"),
        CheckConstraint(
            "status IN ('PENDING','PROCESSING','SENT','FAILED')",
            name="ck_notifications_status",
        ),
        CheckConstraint("channel = 'EMAIL'", name="ck_notifications_channel"),
        CheckConstraint("retry_count >= 0", name="ck_notifications_attempts"),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("loan_applications.id"), index=True
    )
    recipient: Mapped[str] = mapped_column(String(255))
    channel: Mapped[str] = mapped_column(String(20), server_default="EMAIL")
    event_type: Mapped[str] = mapped_column(String(60), index=True)
    subject: Mapped[str] = mapped_column(String(200))
    template: Mapped[str] = mapped_column(String(60))
    event_key: Mapped[str] = mapped_column(String(200), unique=True)
    status: Mapped[str] = mapped_column(String(20), server_default="PENDING")
    retry_count: Mapped[int] = mapped_column(Integer, server_default="0")
    provider_reference: Mapped[str | None] = mapped_column(String(255))
    last_error: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[uuid.UUID | None]
