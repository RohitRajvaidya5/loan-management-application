import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, UUIDPrimaryKeyMixin


class DocumentReview(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "document_reviews"

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id"), index=True
    )
    reviewed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    previous_status: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30))
    remarks: Mapped[str | None] = mapped_column(Text)
    document_version: Mapped[int] = mapped_column(Integer)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
