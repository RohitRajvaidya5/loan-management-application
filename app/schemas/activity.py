from datetime import datetime
from typing import Literal
from uuid import UUID

from app.schemas.common import ORMModel


class ApplicationActivity(ORMModel):
    id: UUID
    source: Literal["note", "status_history", "audit"]
    action: str
    occurred_at: datetime
    actor_id: UUID | None
    actor_name: str | None
    note: str | None
    remarks: str | None
    old_status: str | None
    new_status: str | None
    document_id: UUID | None
