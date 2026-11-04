import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum as SQLAlchemyEnum,
    ForeignKey,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import (
    Base,
    UUIDPrimaryKeyMixin,
)
from app.enums.application_status import ApplicationStatus


class ApplicationStatusHistory(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "application_status_history"

    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("loan_applications.id"),
        nullable=False,
        index=True,
    )

    old_status: Mapped[ApplicationStatus | None] = mapped_column(
        SQLAlchemyEnum(
            ApplicationStatus,
            name="application_status",
            values_callable=lambda enum_class: [
                item.value for item in enum_class
            ],
        ),
        nullable=True,
    )

    new_status: Mapped[ApplicationStatus] = mapped_column(
        SQLAlchemyEnum(
            ApplicationStatus,
            name="application_status",
            values_callable=lambda enum_class: [
                item.value for item in enum_class
            ],
        ),
        nullable=False,
    )

    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    remarks: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    application: Mapped["LoanApplication"] = relationship(
        back_populates="status_history",
    )

    changed_by_user: Mapped["User | None"] = relationship(
        foreign_keys=[changed_by],
    )

    def __repr__(self):
        return (
            f"<ApplicationStatusHistory("
            f"application_id={self.application_id}, "
            f"new_status={self.new_status})>"
        )