import uuid

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class ApplicationNote(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "application_notes"

    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("loan_applications.id"),
        nullable=False,
        index=True,
    )

    author_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    note: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    application: Mapped["LoanApplication"] = relationship(
        back_populates="notes",
    )

    author: Mapped["User"] = relationship(
        back_populates="application_notes",
    )

    def __repr__(self):
        return (
            f"<ApplicationNote("
            f"id={self.id}, "
            f"application_id={self.application_id}, "
            f"author_id={self.author_id})>"
        )
