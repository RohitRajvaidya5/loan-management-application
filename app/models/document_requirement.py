import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, UUIDPrimaryKeyMixin


class DocumentRequirement(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "document_requirements"
    __table_args__ = (UniqueConstraint("loan_type_id", "document_type"),)

    loan_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("loan_types.id"), index=True
    )
    document_type: Mapped[str] = mapped_column(String(100))
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
