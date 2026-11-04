import uuid
from decimal import Decimal

from sqlalchemy import (
    Enum as SQLAlchemyEnum,
)
from sqlalchemy import (
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.enums.application_status import ApplicationStatus


class LoanApplication(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "loan_applications"

    application_number: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        nullable=False,
        index=True,
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id"),
        nullable=False,
        index=True,
    )

    loan_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("loan_types.id"),
        nullable=False,
        index=True,
    )

    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    requested_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
    )

    tenure_months: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    employment_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    monthly_income: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )

    purpose: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[ApplicationStatus] = mapped_column(
        SQLAlchemyEnum(
            ApplicationStatus,
            name="application_status",
            values_callable=lambda enum_class: [item.value for item in enum_class],
        ),
        default=ApplicationStatus.NEW,
        nullable=False,
    )

    customer: Mapped["Customer"] = relationship(
        back_populates="loan_applications",
    )

    loan_type: Mapped["LoanType"] = relationship(
        back_populates="loan_applications",
    )

    assigned_user: Mapped["User | None"] = relationship(
        back_populates="assigned_applications",
        foreign_keys=[assigned_to],
    )

    status_history: Mapped[list["ApplicationStatusHistory"]] = relationship(
        back_populates="application",
        order_by="ApplicationStatusHistory.created_at",
        cascade="all, delete-orphan",
    )

    documents: Mapped[list["Document"]] = relationship(
        back_populates="application",
    )

    notes: Mapped[list["ApplicationNote"]] = relationship(
        back_populates="application",
    )

    def __repr__(self):
        return (
            f"<LoanApplication("
            f"id={self.id}, "
            f"application_number={self.application_number}, "
            f"status={self.status})>"
        )
