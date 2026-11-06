from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class LoginRateLimit(Base):
    __tablename__ = "login_rate_limits"

    peer_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
