import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, UUIDPrimaryKeyMixin


class Document(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "documents"

    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("loan_applications.id"),
        nullable=False,
        index=True,
    )

    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    document_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    storage_key: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        unique=True,
    )

    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    file_size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    application: Mapped["LoanApplication"] = relationship(
        back_populates="documents",
    )

    uploaded_by_user: Mapped["User | None"] = relationship(
        foreign_keys=[uploaded_by],
    )

    def __repr__(self):
        return (
            f"<Document("
            f"id={self.id}, "
            f"document_type={self.document_type}, "
            f"original_filename={self.original_filename})>"
        )
