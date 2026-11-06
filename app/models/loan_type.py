from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)

if TYPE_CHECKING:
    from app.models.loan_application import LoanApplication


class LoanType(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "loan_types"

    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    document_requirements_configured: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    loan_applications: Mapped[list["LoanApplication"]] = relationship(
        back_populates="loan_type",
    )

    def __repr__(self):
        return f"<LoanType(id={self.id}, name={self.name})>"
