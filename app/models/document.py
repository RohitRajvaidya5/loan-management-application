import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.loan_application import LoanApplication
    from app.models.user import User


class Document(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("replaces_document_id", name="uq_documents_replaces"),
    )

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

    status: Mapped[str] = mapped_column(String(30), server_default="PENDING")
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    document_group_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    revision: Mapped[int] = mapped_column(Integer, server_default="1")
    replaces_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", name="fk_documents_replaces")
    )
    replaced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", name="fk_documents_verified_by")
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_remarks: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deletion_remarks: Mapped[str | None] = mapped_column(Text)
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", name="fk_documents_deleted_by")
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
