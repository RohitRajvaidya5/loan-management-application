from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)

if TYPE_CHECKING:
    from app.models.loan_application import LoanApplication


class Customer(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "customers"

    full_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )

    alternate_phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    date_of_birth: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    address: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    city: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    state: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    pincode: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    loan_applications: Mapped[list["LoanApplication"]] = relationship(
        back_populates="customer",
    )

    def __repr__(self):
        return f"<Customer(id={self.id}, full_name={self.full_name})>"
