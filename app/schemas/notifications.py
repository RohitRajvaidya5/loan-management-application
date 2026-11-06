from datetime import datetime
from typing import Literal
from uuid import UUID

from app.schemas.common import ORMModel


class NotificationResponse(ORMModel):
    id: UUID
    application_id: UUID
    recipient: str
    channel: str
    event_type: str
    subject: str
    template: str
    status: Literal["PENDING", "PROCESSING", "SENT", "FAILED"]
    retry_count: int
    last_error: str | None
    provider_reference: str | None
    created_at: datetime
    available_at: datetime
    sent_at: datetime | None
